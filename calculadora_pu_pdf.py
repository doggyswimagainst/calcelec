#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Calculadora interactiva de sistema por unidad con generación de PDF.

El programa pregunta si deseas calcular:
1) Variables base: Sbase, Vbase, Ibase, Zbase.
2) Cantidades en por unidad.
3) Cantidades reales desde por unidad.
4) Cambio de base de impedancias.
5) Voltajes referidos por transformador.

Al finalizar, genera un PDF con el desarrollo de cada cálculo.

Requisitos:
    pip install reportlab

Ejecución:
    python calculadora_pu_pdf.py

Convenciones:
- Sistema trifásico balanceado.
- Potencia base en MVA y kVA.
- Voltaje base en kV línea-línea.
- Corriente base en A.
- Impedancia base en ohm.
- Python usa "j" para complejos:
      50+80j
      0.12j
      1+0j
- También puedes ingresar valores polares:
      polar(1.05, 0)
"""

from __future__ import annotations

import cmath
import html
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union


# ============================================================
# 1. UTILIDADES MATEMÁTICAS Y FORMATO
# ============================================================

Number = Union[float, complex]


def polar(magnitud: float, angulo_grados: float) -> complex:
    """Crea un numero complejo en forma polar."""
    return cmath.rect(magnitud, math.radians(angulo_grados))


def angulo_deg(z: complex) -> float:
    """Angulo de un numero complejo en grados."""
    return math.degrees(cmath.phase(z))


def es_casi_real(z: complex, tol: float = 1e-12) -> bool:
    return abs(z.imag) < tol


def fmt_float(x: float, dec: int = 6) -> str:
    return f"{x:.{dec}f}"


def fmt_rect(z: Number, dec: int = 6) -> str:
    """Formato rectangular para reales o complejos."""
    if isinstance(z, complex):
        if es_casi_real(z):
            return f"{z.real:.{dec}f}"
        signo = "+" if z.imag >= 0 else "-"
        return f"{z.real:.{dec}f} {signo} {abs(z.imag):.{dec}f}j"
    return f"{z:.{dec}f}"


def fmt_polar(z: Number, dec: int = 6) -> str:
    """Formato polar para reales o complejos."""
    if isinstance(z, complex):
        return f"{abs(z):.{dec}f}∠{angulo_deg(z):.{dec}f}°"
    return f"{abs(z):.{dec}f}∠0.000000°"


def pedir_float(mensaje: str) -> float:
    while True:
        entrada = input(mensaje).strip().replace(",", ".")
        try:
            return float(entrada)
        except ValueError:
            print("Entrada invalida. Ejemplo valido: 13.2")


def pedir_complex(mensaje: str) -> complex:
    """
    Permite:
    - 50+80j
    - 0.12j
    - 1+0j
    - polar(1.05, 0)
    - tambien acepta i y lo convierte a j
    """
    while True:
        entrada = input(mensaje).strip().lower().replace("i", "j")
        try:
            if entrada.startswith("polar"):
                return complex(eval(entrada, {"__builtins__": {}}, {"polar": polar}))
            return complex(entrada.replace(" ", ""))
        except Exception:
            print("Entrada invalida. Ejemplos: 50+80j, 0.12j, 1+0j, polar(1.05, 0)")


def pedir_si_no(mensaje: str) -> bool:
    while True:
        entrada = input(mensaje + " [s/n]: ").strip().lower()
        if entrada in ("s", "si", "sí", "y", "yes"):
            return True
        if entrada in ("n", "no"):
            return False
        print("Responde con s o n.")


def pedir_texto(mensaje: str, defecto: Optional[str] = None) -> str:
    entrada = input(mensaje).strip()
    if entrada == "" and defecto is not None:
        return defecto
    return entrada


# ============================================================
# 2. ESTRUCTURA DEL REPORTE
# ============================================================

@dataclass
class SeccionReporte:
    titulo: str
    lineas: List[str]


class Reporte:
    def __init__(self, titulo: str) -> None:
        self.titulo = titulo
        self.secciones: List[SeccionReporte] = []

    def agregar(self, titulo: str, lineas: List[str]) -> None:
        self.secciones.append(SeccionReporte(titulo, lineas))

    def imprimir_consola(self) -> None:
        print("\n" + "=" * 80)
        print(self.titulo)
        print("=" * 80)
        for sec in self.secciones:
            print("\n" + "-" * 80)
            print(sec.titulo)
            print("-" * 80)
            for linea in sec.lineas:
                print(linea)


# ============================================================
# 3. CÁLCULOS DISPONIBLES
# ============================================================

def calcular_variables_base(reporte: Reporte) -> None:
    """
    Calcula Sbase, Ibase y Zbase.
    Permite dos caminos:
    A) ingresar Sbase y Vbase.
    B) ingresar Vbase e Ibase para calcular Sbase.
    """
    print("\nCALCULO DE VARIABLES BASE")
    print("1) Tengo Sbase [MVA] y Vbase [kV]")
    print("2) Tengo Vbase [kV] e Ibase [A], quiero calcular Sbase")

    opcion = pedir_texto("Seleccione opcion [1/2]: ")

    nombre = pedir_texto("Nombre de la zona/base, ejemplo ZONA 1: ", "ZONA")

    lineas: List[str] = []

    if opcion == "1":
        S_MVA = pedir_float("Ingrese Sbase [MVA]: ")
        V_kV = pedir_float("Ingrese Vbase [kV]: ")

        S_kVA = S_MVA * 1000.0
        I_A = S_MVA * 1000.0 / (math.sqrt(3) * V_kV)
        Z_ohm_1 = V_kV**2 / S_MVA
        Z_ohm_2 = V_kV *1000.0 / (math.sqrt(3) * I_A)

        lineas += [
            f"{nombre}",
            f"Datos:",
            f"Sbase = {S_MVA:.6f} MVA",
            f"Vbase = {V_kV:.6f} kV",
            "",
            "Potencia base aparente:",
            "Sbase = Sbase",
            f"Sbase = {S_MVA:.6f} MVA = {S_kVA:.3f} kVA",
            "",
            "Corriente base:",
            "Ibase = Sbase/(sqrt(3)*Vbase)",
            f"Ibase = {S_MVA:.6f} MVA/(sqrt(3)*{V_kV:.6f} kV)",
            f"Ibase = {I_A:.6f} A",
            "",
            "Impedancia base:",
            "Zbase = Vbase^2/Sbase",
            f"Zbase = ({V_kV:.6f} kV)^2/{S_MVA:.6f} MVA",
            f"Zbase = {Z_ohm_1:.6f} ohm",
            "",
            "Comprobacion alternativa:",
            "Zbase = Vbase/(sqrt(3)*Ibase)",
            f"Zbase = {V_kV:.6f} kV/(sqrt(3)*{I_A:.6f} A)",
            f"Zbase = {Z_ohm_2:.6f} ohm",
        ]

    elif opcion == "2":
        V_kV = pedir_float("Ingrese Vbase [kV]: ")
        I_A = pedir_float("Ingrese Ibase [A]: ")

        S_MVA = math.sqrt(3) * V_kV * I_A / 1000.0
        S_kVA = S_MVA * 1000.0
        Z_ohm_1 = V_kV *1000.0 / (math.sqrt(3) * I_A)
        Z_ohm_2 = V_kV**2 / S_MVA

        lineas += [
            f"{nombre}",
            f"Datos:",
            f"Vbase = {V_kV:.6f} kV",
            f"Ibase = {I_A:.6f} A",
            "",
            "Potencia base aparente:",
            "Sbase = sqrt(3)*Vbase*Ibase",
            f"Sbase = sqrt(3)*{V_kV:.6f} kV*{I_A:.6f} A",
            f"Sbase = {S_MVA:.6f} MVA = {S_kVA:.3f} kVA",
            "",
            "Impedancia base:",
            "Zbase = Vbase/(sqrt(3)*Ibase)",
            f"Zbase = {V_kV:.6f} kV/(sqrt(3)*{I_A:.6f} A)",
            f"Zbase = {Z_ohm_1:.6f} ohm",
            "",
            "Comprobacion alternativa:",
            "Zbase = Vbase^2/Sbase",
            f"Zbase = ({V_kV:.6f} kV)^2/{S_MVA:.6f} MVA",
            f"Zbase = {Z_ohm_2:.6f} ohm",
        ]

    else:
        print("Opcion no valida. No se agrego calculo.")
        return

    reporte.agregar("Calculo de variables base", lineas)
    print("\n".join(lineas))


def calcular_por_unidad(reporte: Reporte) -> None:
    """
    Calcula Variable_pu = Variable_real/Variable_base.
    Sirve para voltaje, corriente, potencia, impedancia u otra magnitud.
    """
    print("\nCALCULO DE VARIABLE EN POR UNIDAD")

    nombre = pedir_texto("Nombre de la variable, ejemplo V, I, Z, S: ", "Variable")
    unidad = pedir_texto("Unidad de la variable, ejemplo kV, A, ohm, MVA: ", "")

    valor_real = pedir_complex(f"Ingrese {nombre}_real [{unidad}], ejemplo 13.2, 50+80j: ")
    valor_base = pedir_float(f"Ingrese {nombre}_base [{unidad}]: ")

    valor_pu = valor_real / valor_base

    lineas = [
        f"Datos:",
        f"{nombre}_real = {fmt_rect(valor_real)} {unidad}",
        f"{nombre}_base = {valor_base:.6f} {unidad}",
        "",
        "Cantidad en por unidad:",
        f"{nombre}_p.u = {nombre}_real/{nombre}_base",
        f"{nombre}_p.u = ({fmt_rect(valor_real)})/{valor_base:.6f}",
        f"{nombre}_p.u = {fmt_rect(valor_pu)}",
        f"{nombre}_p.u = {fmt_polar(valor_pu)}",
    ]

    reporte.agregar(f"Calculo de {nombre} en por unidad", lineas)
    print("\n".join(lineas))


def calcular_variable_real(reporte: Reporte) -> None:
    """
    Calcula Variable_real = Variable_base*Variable_pu.
    """
    print("\nCALCULO DE VARIABLE REAL DESDE P.U.")

    nombre = pedir_texto("Nombre de la variable, ejemplo V, I, Z, S: ", "Variable")
    unidad = pedir_texto("Unidad real, ejemplo kV, A, ohm, MVA: ", "")

    valor_pu = pedir_complex(f"Ingrese {nombre}_p.u, ejemplo 0.8+0.2j o polar(1.05,0): ")
    valor_base = pedir_float(f"Ingrese {nombre}_base [{unidad}]: ")

    valor_real = valor_base * valor_pu

    lineas = [
        f"Datos:",
        f"{nombre}_p.u = {fmt_rect(valor_pu)} = {fmt_polar(valor_pu)}",
        f"{nombre}_base = {valor_base:.6f} {unidad}",
        "",
        "Cantidad real:",
        f"{nombre}_real = {nombre}_base*{nombre}_p.u",
        f"{nombre}_real = {valor_base:.6f}*({fmt_rect(valor_pu)}) {unidad}",
        f"{nombre}_real = {fmt_rect(valor_real)} {unidad}",
        f"{nombre}_real = {fmt_polar(valor_real)} {unidad}",
    ]

    reporte.agregar(f"Calculo de {nombre} real desde p.u.", lineas)
    print("\n".join(lineas))


def calcular_cambio_base_impedancia(reporte: Reporte) -> None:
    """
    Cambio de base de impedancia:
    Zpu_2 = Zpu_1*(Sbase2/Sbase1)*(Vbase1/Vbase2)^2
    """
    print("\nCAMBIO DE BASE DE IMPEDANCIA")

    nombre = pedir_texto("Nombre de la impedancia, ejemplo XG1, XT1, ZL1: ", "Z")

    Z_pu_1 = pedir_complex(f"Ingrese {nombre}_p.u en base 1, ejemplo 0.12j: ")
    Sbase_1 = pedir_float("Ingrese Sbase1 [MVA]: ")
    Vbase_1 = pedir_float("Ingrese Vbase1 [kV]: ")
    Sbase_2 = pedir_float("Ingrese Sbase2 [MVA]: ")
    Vbase_2 = pedir_float("Ingrese Vbase2 [kV]: ")

    Z_pu_2 = Z_pu_1 * (Sbase_2 / Sbase_1) * (Vbase_1 / Vbase_2) ** 2

    # Tambien se muestra con Zbase para mayor claridad
    Zbase_1 = Vbase_1**2 / Sbase_1
    Zbase_2 = Vbase_2**2 / Sbase_2
    Z_real = Z_pu_1 * Zbase_1
    Z_pu_2_check = Z_real / Zbase_2

    lineas = [
        f"Datos:",
        f"{nombre}_p.u,base1 = {fmt_rect(Z_pu_1)} = {fmt_polar(Z_pu_1)}",
        f"Sbase1 = {Sbase_1:.6f} MVA",
        f"Vbase1 = {Vbase_1:.6f} kV",
        f"Sbase2 = {Sbase_2:.6f} MVA",
        f"Vbase2 = {Vbase_2:.6f} kV",
        "",
        "Cambio de base:",
        f"{nombre}_p.u,base2 = {nombre}_p.u,base1*(Sbase2/Sbase1)*(Vbase1/Vbase2)^2",
        f"{nombre}_p.u,base2 = ({fmt_rect(Z_pu_1)})*({Sbase_2:.6f}/{Sbase_1:.6f})*({Vbase_1:.6f}/{Vbase_2:.6f})^2",
        f"{nombre}_p.u,base2 = {fmt_rect(Z_pu_2)}",
        f"{nombre}_p.u,base2 = {fmt_polar(Z_pu_2)}",
        "",
        "Comprobacion mediante impedancia real:",
        "Zbase1 = Vbase1^2/Sbase1",
        f"Zbase1 = ({Vbase_1:.6f} kV)^2/{Sbase_1:.6f} MVA = {Zbase_1:.6f} ohm",
        "Zreal = Zpu1*Zbase1",
        f"Zreal = ({fmt_rect(Z_pu_1)})*{Zbase_1:.6f} = {fmt_rect(Z_real)} ohm",
        "Zbase2 = Vbase2^2/Sbase2",
        f"Zbase2 = ({Vbase_2:.6f} kV)^2/{Sbase_2:.6f} MVA = {Zbase_2:.6f} ohm",
        "Zpu2 = Zreal/Zbase2",
        f"Zpu2 = ({fmt_rect(Z_real)})/{Zbase_2:.6f} = {fmt_rect(Z_pu_2_check)}",
    ]

    reporte.agregar(f"Cambio de base de {nombre}", lineas)
    print("\n".join(lineas))


def calcular_voltaje_referido(reporte: Reporte) -> None:
    """
    Refiere voltaje de un lado de transformador a otro:
    V_ref = V_origen*V_destino_nom/V_origen_nom
    """
    print("\nVOLTAJE REFERIDO POR TRANSFORMADOR")

    nombre = pedir_texto("Nombre del voltaje, ejemplo Vgenerador, Vbase2: ", "V")
    V_origen = pedir_float(f"Ingrese {nombre}_origen [kV]: ")
    V_nom_origen = pedir_float("Ingrese voltaje nominal del lado origen del transformador [kV]: ")
    V_nom_destino = pedir_float("Ingrese voltaje nominal del lado destino del transformador [kV]: ")

    V_ref = V_origen * V_nom_destino / V_nom_origen

    lineas = [
        f"Datos:",
        f"{nombre}_origen = {V_origen:.6f} kV",
        f"Vnom_origen = {V_nom_origen:.6f} kV",
        f"Vnom_destino = {V_nom_destino:.6f} kV",
        "",
        "Voltaje referido:",
        f"{nombre}_referido = {nombre}_origen*Vnom_destino/Vnom_origen",
        f"{nombre}_referido = {V_origen:.6f}*{V_nom_destino:.6f}/{V_nom_origen:.6f}",
        f"{nombre}_referido = {V_ref:.6f} kV",
    ]

    reporte.agregar(f"Voltaje referido - {nombre}", lineas)
    print("\n".join(lineas))


# ============================================================
# 4. GENERACIÓN DEL PDF
# ============================================================

def generar_pdf(reporte: Reporte, ruta_pdf: str) -> Path:
    """
    Genera un PDF con ReportLab.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
    except ImportError as exc:
        raise ImportError(
            "No se encontro reportlab. Instala la dependencia con: pip install reportlab"
        ) from exc

    salida = Path(ruta_pdf).expanduser().resolve()
    if salida.suffix.lower() != ".pdf":
        salida = salida.with_suffix(".pdf")

    doc = SimpleDocTemplate(
        str(salida),
        pagesize=letter,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.7 * cm,
        bottomMargin=1.7 * cm,
    )

    styles = getSampleStyleSheet()
    titulo_style = styles["Title"]
    h1 = styles["Heading1"]
    normal = styles["Normal"]

    mono = ParagraphStyle(
        "Mono",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.5,
        leading=10.5,
        spaceAfter=8,
    )

    story = []

    story.append(Paragraph(html.escape(reporte.titulo), titulo_style))
    story.append(Paragraph(f"Generado: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", normal))
    story.append(Spacer(1, 12))

    if not reporte.secciones:
        story.append(Paragraph("No se registraron calculos.", normal))
    else:
        for idx, sec in enumerate(reporte.secciones, start=1):
            story.append(Paragraph(html.escape(f"{idx}. {sec.titulo}"), h1))
            bloque = "\n".join(sec.lineas)
            story.append(Preformatted(bloque, mono))
            story.append(Spacer(1, 8))

    doc.build(story)
    return salida


def generar_txt_respaldo(reporte: Reporte, ruta_txt: str) -> Path:
    """
    Genera un txt de respaldo si el usuario quiere guardar el desarrollo sin PDF.
    """
    salida = Path(ruta_txt).expanduser().resolve()
    if salida.suffix.lower() != ".txt":
        salida = salida.with_suffix(".txt")

    lineas = [reporte.titulo, f"Generado: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", ""]
    for idx, sec in enumerate(reporte.secciones, start=1):
        lineas.append("=" * 80)
        lineas.append(f"{idx}. {sec.titulo}")
        lineas.append("=" * 80)
        lineas.extend(sec.lineas)
        lineas.append("")

    salida.write_text("\n".join(lineas), encoding="utf-8")
    return salida


# ============================================================
# 5. MENÚ PRINCIPAL
# ============================================================

def menu() -> None:
    reporte = Reporte("Desarrollo de calculos en sistema por unidad")

    while True:
        print("\n" + "=" * 80)
        print("CALCULADORA P.U. CON DESARROLLO EN PDF")
        print("=" * 80)
        print("1) Calcular variables base")
        print("2) Calcular cantidad en por unidad")
        print("3) Calcular cantidad real desde p.u.")
        print("4) Cambio de base de impedancia")
        print("5) Voltaje referido por transformador")
        print("6) Ver desarrollo acumulado en consola")
        print("7) Generar PDF y salir")
        print("8) Generar TXT de respaldo y salir")
        print("0) Salir sin generar archivo")

        opcion = input("Seleccione una opcion: ").strip()

        if opcion == "1":
            calcular_variables_base(reporte)

        elif opcion == "2":
            calcular_por_unidad(reporte)

        elif opcion == "3":
            calcular_variable_real(reporte)

        elif opcion == "4":
            calcular_cambio_base_impedancia(reporte)

        elif opcion == "5":
            calcular_voltaje_referido(reporte)

        elif opcion == "6":
            reporte.imprimir_consola()

        elif opcion == "7":
            nombre_pdf = pedir_texto("Nombre del PDF de salida [desarrollo_pu.pdf]: ", "desarrollo_pu.pdf")
            try:
                salida = generar_pdf(reporte, nombre_pdf)
                print(f"PDF generado correctamente: {salida}")
            except ImportError as exc:
                print(str(exc))
                if pedir_si_no("¿Desea generar un TXT de respaldo?"):
                    salida = generar_txt_respaldo(reporte, "desarrollo_pu.txt")
                    print(f"TXT generado correctamente: {salida}")
            break

        elif opcion == "8":
            nombre_txt = pedir_texto("Nombre del TXT de salida [desarrollo_pu.txt]: ", "desarrollo_pu.txt")
            salida = generar_txt_respaldo(reporte, nombre_txt)
            print(f"TXT generado correctamente: {salida}")
            break

        elif opcion == "0":
            print("Salida sin generar archivo.")
            break

        else:
            print("Opcion no valida.")


if __name__ == "__main__":
    menu()
