import math
import cmath
import html
import io
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import utility functions from calculadora_pu_pdf
from calculadora_pu_pdf import polar, angulo_deg, es_casi_real, fmt_rect, fmt_polar, fmt_float

app = FastAPI(title="Calculadora Per-Unit Profesional")

# CORS setup for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Standard voltages in kV line-line
STANDARD_VOLTAGES = [
    0.12, 0.22, 0.38, 0.4, 0.48, 1.0, 2.3, 4.16, 12.0, 13.2, 13.8, 23.0, 
    34.5, 44.0, 66.0, 110.0, 114.0, 115.0, 154.0, 220.0, 500.0
]

def check_voltage_standard(v_kv: float) -> tuple[bool, Optional[str]]:
    if v_kv <= 0:
        return False, "El voltaje debe ser mayor a cero."
    # Check if within 3% tolerance of standard values
    for std in STANDARD_VOLTAGES:
        if abs(v_kv - std) / std <= 0.03:
            return True, None
    return False, f"¿Voltaje no estándar? ({v_kv:.3f} kV no coincide con valores comerciales estándar)."

def to_mva(val: float, unit: str) -> float:
    u = unit.upper()
    if u in ("W", "VA"):
        return val * 1e-6
    elif u in ("KW", "KVA"):
        return val * 1e-3
    elif u in ("MW", "MVA"):
        return val
    return val

def to_kv(val: float, unit: str) -> float:
    u = unit.upper()
    if u == "V":
        return val * 1e-3
    elif u == "KV":
        return val
    return val

def to_a(val: float, unit: str) -> float:
    if unit == "kA":
        return val * 1000.0
    return val

# --- MODELS ---

class ComplexNumberModel(BaseModel):
    real: float = 0.0
    imag: float = 0.0
    mag: float = 0.0
    ang: float = 0.0
    format: str = "rect" # "rect" or "polar"

    def to_complex(self) -> complex:
        if self.format == "polar":
            return polar(self.mag, self.ang)
        return complex(self.real, self.imag)

    @classmethod
    def from_complex(cls, z: complex) -> "ComplexNumberModel":
        mag = abs(z)
        ang = angulo_deg(z)
        return cls(
            real=z.real,
            imag=z.imag,
            mag=mag,
            ang=ang,
            format="rect"
        )

class BaseRequest(BaseModel):
    opcion: str # "1" or "2"
    nombre: str
    sbase: Optional[float] = 0.0
    sbase_unit: str = "MVA"
    vbase: Optional[float] = 0.0
    vbase_unit: str = "kV"
    ibase: Optional[float] = 0.0
    ibase_unit: str = "A"

class UnifilarRequest(BaseModel):
    sbase: float
    sbase_unit: str = "MVA"
    vbase1: float
    vbase1_unit: str = "kV"
    t1_prim: float
    t1_sec: float
    t2_prim: float
    t2_sec: float

class PuRequest(BaseModel):
    nombre: str
    unidad: str
    valor_real: ComplexNumberModel
    valor_base: float

class RealRequest(BaseModel):
    nombre: str
    unidad: str
    valor_pu: ComplexNumberModel
    valor_base: float

class CambioBaseRequest(BaseModel):
    nombre: str
    is_percentage: bool
    x_pct: float = 0.0
    z_pu1: Optional[ComplexNumberModel] = None
    sbase1: float
    sbase1_unit: str = "MVA"
    vbase1: float
    vbase1_unit: str = "kV"
    sbase2: float
    sbase2_unit: str = "MVA"
    vbase2: float
    vbase2_unit: str = "kV"

class VoltajeReferidoRequest(BaseModel):
    nombre: str
    v_origen: float
    v_origen_unit: str = "kV"
    v_nom_origen: float
    v_nom_origen_unit: str = "kV"
    v_nom_destino: float
    v_nom_destino_unit: str = "kV"

class HistoryItem(BaseModel):
    tipo: str # "base", "unifilar", "pu", "real", "cambio_base", "voltaje_referido"
    titulo: str
    datos_entrada: Dict[str, Any]
    datos_salida: Dict[str, Any]
    desglose: List[str]

class PdfRequest(BaseModel):
    titulo: str = "Reporte de Cálculos en Sistema por Unidad"
    historial: List[HistoryItem]

# --- ENDPOINTS ---

@app.post("/api/calcular-base")
def api_calcular_base(req: BaseRequest):
    nombre = req.nombre or "ZONA"
    desglose = []
    
    sbase_val = req.sbase if req.sbase is not None else 0.0
    vbase_val = req.vbase if req.vbase is not None else 0.0
    ibase_val = req.ibase if req.ibase is not None else 0.0
    
    if req.opcion == "1":
        # Convert Sbase and Vbase
        S_MVA = to_mva(sbase_val, req.sbase_unit)
        V_kV = to_kv(vbase_val, req.vbase_unit)
        
        if V_kV <= 0 or S_MVA <= 0:
            raise HTTPException(status_code=400, detail="Los valores base de potencia y tensión deben ser mayores a cero.")
            
        S_kVA = S_MVA * 1000.0
        I_A = S_MVA * 1000.0 / (math.sqrt(3) * V_kV)
        Z_ohm = V_kV**2 / S_MVA
        
        is_std, warning_msg = check_voltage_standard(V_kV)
        
        desglose = [
            f"Zona / Base: {nombre}",
            f"Datos de entrada:",
            f"  Sbase = {req.sbase:.6f} {req.sbase_unit} ({S_MVA:.6f} MVA)",
            f"  Vbase = {req.vbase:.6f} {req.vbase_unit} ({V_kV:.6f} kV)",
            "",
            "1. Potencia base aparente:",
            "  Sbase = Sbase",
            f"  Sbase = {S_MVA:.6f} MVA = {S_kVA:.3f} kVA",
            "",
            "2. Corriente base:",
            "  Ibase = Sbase / (sqrt(3) * Vbase)",
            f"  Ibase = {S_MVA:.6f} MVA / (sqrt(3) * {V_kV:.6f} kV)",
            f"  Ibase = {I_A:.6f} A",
            "",
            "3. Impedancia base:",
            "  Zbase = Vbase^2 / Sbase",
            f"  Zbase = ({V_kV:.6f} kV)^2 / {S_MVA:.6f} MVA",
            f"  Zbase = {Z_ohm:.6f} ohm",
            "",
            "4. Comprobación alternativa (Zbase = Vbase / (sqrt(3) * Ibase)):",
            f"  Zbase = {V_kV:.6f} kV / (sqrt(3) * {I_A:.6f} A) = {V_kV * 1000.0 / (math.sqrt(3) * I_A):.6f} ohm"
        ]
        
        return {
            "sbase_mva": S_MVA,
            "sbase_kva": S_kVA,
            "vbase_kv": V_kV,
            "ibase_a": I_A,
            "zbase_ohm": Z_ohm,
            "vbase_warning": warning_msg,
            "desglose": desglose
        }
        
    elif req.opcion == "2":
        V_kV = to_kv(vbase_val, req.vbase_unit)
        I_A = to_a(ibase_val, req.ibase_unit)
        
        if V_kV <= 0 or I_A <= 0:
            raise HTTPException(status_code=400, detail="Los valores base de corriente y tensión deben ser mayores a cero.")
            
        S_MVA = math.sqrt(3) * V_kV * I_A / 1000.0
        S_kVA = S_MVA * 1000.0
        Z_ohm = V_kV * 1000.0 / (math.sqrt(3) * I_A)
        
        is_std, warning_msg = check_voltage_standard(V_kV)
        
        desglose = [
            f"Zona / Base: {nombre}",
            f"Datos de entrada:",
            f"  Vbase = {req.vbase:.6f} {req.vbase_unit} ({V_kV:.6f} kV)",
            f"  Ibase = {req.ibase:.6f} {req.ibase_unit} ({I_A:.6f} A)",
            "",
            "1. Potencia base aparente:",
            "  Sbase = sqrt(3) * Vbase * Ibase",
            f"  Sbase = sqrt(3) * {V_kV:.6f} kV * {I_A:.6f} A",
            f"  Sbase = {S_MVA:.6f} MVA = {S_kVA:.3f} kVA",
            "",
            "2. Impedancia base:",
            "  Zbase = Vbase / (sqrt(3) * Ibase)",
            f"  Zbase = {V_kV:.6f} kV / (sqrt(3) * {I_A:.6f} A)",
            f"  Zbase = {Z_ohm:.6f} ohm",
            "",
            "3. Comprobación alternativa (Zbase = Vbase^2 / Sbase):",
            f"  Zbase = ({V_kV:.6f} kV)^2 / {S_MVA:.6f} MVA = {V_kV**2 / S_MVA:.6f} ohm"
        ]
        
        return {
            "sbase_mva": S_MVA,
            "sbase_kva": S_kVA,
            "vbase_kv": V_kV,
            "ibase_a": I_A,
            "zbase_ohm": Z_ohm,
            "vbase_warning": warning_msg,
            "desglose": desglose
        }
    else:
        raise HTTPException(status_code=400, detail="Opción inválida.")

@app.post("/api/unifilar-zonas")
def api_unifilar_zonas(req: UnifilarRequest):
    S_MVA = to_mva(req.sbase, req.sbase_unit)
    V_kV_1 = to_kv(req.vbase1, req.vbase1_unit)
    
    if S_MVA <= 0 or V_kV_1 <= 0:
        raise HTTPException(status_code=400, detail="La potencia base y la tensión base de la Zona 1 deben ser mayores a cero.")
    if req.t1_prim <= 0 or req.t1_sec <= 0 or req.t2_prim <= 0 or req.t2_sec <= 0:
        raise HTTPException(status_code=400, detail="Las relaciones de transformación de los transformadores deben ser mayores a cero.")
        
    # Zona 1
    I_A_1 = S_MVA * 1000.0 / (math.sqrt(3) * V_kV_1)
    Z_ohm_1 = V_kV_1**2 / S_MVA
    v1_std, v1_warn = check_voltage_standard(V_kV_1)
    
    # Zona 2
    V_kV_2 = V_kV_1 * (req.t1_sec / req.t1_prim)
    I_A_2 = S_MVA * 1000.0 / (math.sqrt(3) * V_kV_2)
    Z_ohm_2 = V_kV_2**2 / S_MVA
    v2_std, v2_warn = check_voltage_standard(V_kV_2)
    
    # Zona 3
    V_kV_3 = V_kV_2 * (req.t2_sec / req.t2_prim)
    I_A_3 = S_MVA * 1000.0 / (math.sqrt(3) * V_kV_3)
    Z_ohm_3 = V_kV_3**2 / S_MVA
    v3_std, v3_warn = check_voltage_standard(V_kV_3)
    
    desglose = [
        f"SISTEMA UNIFILAR LINEAL DE 3 ZONAS",
        f"Potencia Base General: {S_MVA:.6f} MVA",
        "",
        "--- ZONA 1 (Generación) ---",
        f"Vbase1 = {V_kV_1:.6f} kV",
        f"Ibase1 = Sbase / (sqrt(3)*Vbase1)",
        f"Ibase1 = {S_MVA:.6f}*1000 / (sqrt(3)*{V_kV_1:.6f}) = {I_A_1:.6f} A",
        f"Zbase1 = Vbase1^2 / Sbase = ({V_kV_1:.6f})^2 / {S_MVA:.6f} = {Z_ohm_1:.6f} ohm",
        "",
        "--- ZONA 2 (Transmisión) ---",
        f"Relación de Transformador T1: {req.t1_prim:.3f} kV / {req.t1_sec:.3f} kV",
        "Vbase2 = Vbase1 * (Vnom_sec_T1 / Vnom_prim_T1)",
        f"Vbase2 = {V_kV_1:.6f} * ({req.t1_sec:.6f} / {req.t1_prim:.6f}) = {V_kV_2:.6f} kV",
        f"Ibase2 = Sbase / (sqrt(3)*Vbase2)",
        f"Ibase2 = {S_MVA:.6f}*1000 / (sqrt(3)*{V_kV_2:.6f}) = {I_A_2:.6f} A",
        f"Zbase2 = Vbase2^2 / Sbase = ({V_kV_2:.6f})^2 / {S_MVA:.6f} = {Z_ohm_2:.6f} ohm",
        "",
        "--- ZONA 3 (Distribución) ---",
        f"Relación de Transformador T2: {req.t2_prim:.3f} kV / {req.t2_sec:.3f} kV",
        "Vbase3 = Vbase2 * (Vnom_sec_T2 / Vnom_prim_T2)",
        f"Vbase3 = {V_kV_2:.6f} * ({req.t2_sec:.6f} / {req.t2_prim:.6f}) = {V_kV_3:.6f} kV",
        f"Ibase3 = Sbase / (sqrt(3)*Vbase3)",
        f"Ibase3 = {S_MVA:.6f}*1000 / (sqrt(3)*{V_kV_3:.6f}) = {I_A_3:.6f} A",
        f"Zbase3 = Vbase3^2 / Sbase = ({V_kV_3:.6f})^2 / {S_MVA:.6f} = {Z_ohm_3:.6f} ohm",
    ]
    
    return {
        "zones": [
            {
                "name": "Zona 1 (Generación)",
                "sbase_mva": S_MVA,
                "vbase_kv": V_kV_1,
                "ibase_a": I_A_1,
                "zbase_ohm": Z_ohm_1,
                "is_standard": v1_std,
                "warning": v1_warn
            },
            {
                "name": "Zona 2 (Transmisión)",
                "sbase_mva": S_MVA,
                "vbase_kv": V_kV_2,
                "ibase_a": I_A_2,
                "zbase_ohm": Z_ohm_2,
                "is_standard": v2_std,
                "warning": v2_warn
            },
            {
                "name": "Zona 3 (Distribución)",
                "sbase_mva": S_MVA,
                "vbase_kv": V_kV_3,
                "ibase_a": I_A_3,
                "zbase_ohm": Z_ohm_3,
                "is_standard": v3_std,
                "warning": v3_warn
            }
        ],
        "desglose": desglose
    }

@app.post("/api/pasar-pu")
def api_pasar_pu(req: PuRequest):
    if req.valor_base <= 0:
        raise HTTPException(status_code=400, detail="El valor base debe ser mayor a cero.")
        
    z_real = req.valor_real.to_complex()
    z_pu = z_real / req.valor_base
    
    desglose = [
        f"Datos:",
        f"  {req.nombre}_real = {fmt_rect(z_real)} {req.unidad} (Rectangular)",
        f"  {req.nombre}_real = {fmt_polar(z_real)} {req.unidad} (Polar)",
        f"  {req.nombre}_base = {req.valor_base:.6f} {req.unidad}",
        "",
        "Cálculo en por unidad (p.u.):",
        f"  {req.nombre}_pu = {req.nombre}_real / {req.nombre}_base",
        f"  {req.nombre}_pu = ({fmt_rect(z_real)}) / {req.valor_base:.6f}",
        f"  {req.nombre}_pu = {fmt_rect(z_pu)} p.u. (Rectangular)",
        f"  {req.nombre}_pu = {fmt_polar(z_pu)} p.u. (Polar)"
    ]
    
    return {
        "valor_pu": ComplexNumberModel.from_complex(z_pu),
        "fmt_rect": fmt_rect(z_pu),
        "fmt_polar": fmt_polar(z_pu),
        "desglose": desglose
    }

@app.post("/api/pasar-real")
def api_pasar_real(req: RealRequest):
    if req.valor_base <= 0:
        raise HTTPException(status_code=400, detail="El valor base debe ser mayor a cero.")
        
    z_pu = req.valor_pu.to_complex()
    z_real = z_pu * req.valor_base
    
    desglose = [
        f"Datos:",
        f"  {req.nombre}_pu = {fmt_rect(z_pu)} (Rectangular)",
        f"  {req.nombre}_pu = {fmt_polar(z_pu)} (Polar)",
        f"  {req.nombre}_base = {req.valor_base:.6f} {req.unidad}",
        "",
        "Cálculo de magnitud real:",
        f"  {req.nombre}_real = {req.nombre}_base * {req.nombre}_pu",
        f"  {req.nombre}_real = {req.valor_base:.6f} * ({fmt_rect(z_pu)})",
        f"  {req.nombre}_real = {fmt_rect(z_real)} {req.unidad} (Rectangular)",
        f"  {req.nombre}_real = {fmt_polar(z_real)} {req.unidad} (Polar)"
    ]
    
    return {
        "valor_real": ComplexNumberModel.from_complex(z_real),
        "fmt_rect": fmt_rect(z_real),
        "fmt_polar": fmt_polar(z_real),
        "desglose": desglose
    }

@app.post("/api/cambio-base")
def api_cambio_base(req: CambioBaseRequest):
    S1 = to_mva(req.sbase1, req.sbase1_unit)
    V1 = to_kv(req.vbase1, req.vbase1_unit)
    S2 = to_mva(req.sbase2, req.sbase2_unit)
    V2 = to_kv(req.vbase2, req.vbase2_unit)
    
    if S1 <= 0 or V1 <= 0 or S2 <= 0 or V2 <= 0:
        raise HTTPException(status_code=400, detail="Todos los valores base de potencia y tensión deben ser mayores a cero.")
        
    nombre = req.nombre or "Z"
    
    if req.is_percentage:
        # X% = 7.5% -> Xpu = 0.075 -> Zpu1 = 0 + 0.075j
        reactance_pu = req.x_pct / 100.0
        z_pu1 = complex(0.0, reactance_pu)
    else:
        if not req.z_pu1:
            raise HTTPException(status_code=400, detail="Debe ingresar la impedancia en base 1 si no es reactancia de placa.")
        z_pu1 = req.z_pu1.to_complex()
        
    z_pu2 = z_pu1 * (S2 / S1) * (V1 / V2) ** 2
    
    # Verification using real impedance
    Zbase1 = V1**2 / S1
    Zbase2 = V2**2 / S2
    Zreal = z_pu1 * Zbase1
    z_pu2_check = Zreal / Zbase2
    
    input_str = f"Reactancia de placa = {req.x_pct:.3f}%" if req.is_percentage else f"Zpu1 = {fmt_rect(z_pu1)} = {fmt_polar(z_pu1)}"
    
    desglose = [
        f"Impedancia: {nombre}",
        f"Datos:",
        f"  Base 1: {input_str}",
        f"  Sbase1 = {S1:.6f} MVA, Vbase1 = {V1:.6f} kV",
        f"  Base 2 (Nueva):",
        f"  Sbase2 = {S2:.6f} MVA, Vbase2 = {V2:.6f} kV",
        "",
        "1. Cambio de base directo:",
        "  Zpu2 = Zpu1 * (Sbase2 / Sbase1) * (Vbase1 / Vbase2)^2",
        f"  Zpu2 = ({fmt_rect(z_pu1)}) * ({S2:.6f} / {S1:.6f}) * ({V1:.6f} / {V2:.6f})^2",
        f"  Zpu2 = {fmt_rect(z_pu2)} (Rectangular)",
        f"  Zpu2 = {fmt_polar(z_pu2)} (Polar)",
        "",
        "2. Comprobación mediante impedancia física (ohm):",
        "  Zbase1 = Vbase1^2 / Sbase1",
        f"  Zbase1 = ({V1:.6f} kV)^2 / {S1:.6f} MVA = {Zbase1:.6f} ohm",
        "  Zreal = Zpu1 * Zbase1",
        f"  Zreal = ({fmt_rect(z_pu1)}) * {Zbase1:.6f} = {fmt_rect(Zreal)} ohm",
        "  Zbase2 = Vbase2^2 / Sbase2",
        f"  Zbase2 = ({V2:.6f} kV)^2 / {S2:.6f} MVA = {Zbase2:.6f} ohm",
        "  Zpu2 (comprobado) = Zreal / Zbase2",
        f"  Zpu2 (comprobado) = ({fmt_rect(Zreal)}) / {Zbase2:.6f} = {fmt_rect(z_pu2_check)}"
    ]
    
    return {
        "z_pu2": ComplexNumberModel.from_complex(z_pu2),
        "fmt_rect": fmt_rect(z_pu2),
        "fmt_polar": fmt_polar(z_pu2),
        "zbase1_ohm": Zbase1,
        "zbase2_ohm": Zbase2,
        "zreal_ohm": ComplexNumberModel.from_complex(Zreal),
        "fmt_zreal_ohm": fmt_rect(Zreal),
        "desglose": desglose
    }

@app.post("/api/voltaje-referido")
def api_voltaje_referido(req: VoltajeReferidoRequest):
    V_orig = to_kv(req.v_origen, req.v_origen_unit)
    V_nom_orig = to_kv(req.v_nom_origen, req.v_nom_origen_unit)
    V_nom_dest = to_kv(req.v_nom_destino, req.v_nom_destino_unit)
    
    if V_orig <= 0 or V_nom_orig <= 0 or V_nom_dest <= 0:
        raise HTTPException(status_code=400, detail="Todas las tensiones nominales y de origen deben ser mayores a cero.")
        
    V_ref = V_orig * V_nom_dest / V_nom_orig
    
    is_std_orig, warning_orig = check_voltage_standard(V_nom_orig)
    is_std_dest, warning_dest = check_voltage_standard(V_nom_dest)
    is_std_ref, warning_ref = check_voltage_standard(V_ref)
    
    desglose = [
        f"Referido de tensión: {req.nombre}",
        f"Datos:",
        f"  V_origen = {req.v_origen:.6f} {req.v_origen_unit} ({V_orig:.6f} kV)",
        f"  Vnom_origen_T = {req.v_nom_origen:.6f} {req.v_nom_origen_unit} ({V_nom_orig:.6f} kV)",
        f"  Vnom_destino_T = {req.v_nom_destino:.6f} {req.v_nom_destino_unit} ({V_nom_dest:.6f} kV)",
        "",
        "Fórmula de voltaje referido:",
        "  V_referido = V_origen * Vnom_destino / Vnom_origen",
        f"  V_referido = {V_orig:.6f} * {V_nom_dest:.6f} / {V_nom_orig:.6f}",
        f"  V_referido = {V_ref:.6f} kV"
    ]
    
    # Combined warning
    warning_msg = None
    if warning_orig:
        warning_msg = f"Origen: {warning_orig}"
    if warning_dest:
        warning_msg = (warning_msg + " | " if warning_msg else "") + f"Destino: {warning_dest}"
    if warning_ref:
        warning_msg = (warning_msg + " | " if warning_msg else "") + f"Referido: {warning_ref}"
        
    return {
        "v_referido_kv": V_ref,
        "warning": warning_msg,
        "desglose": desglose
    }

# --- PDF GENERATOR ---

@app.post("/api/exportar-pdf")
def api_exportar_pdf(req: PdfRequest):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Preformatted
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="La librería ReportLab no está disponible en el servidor."
        )

    # Numbered Canvas for "Página X de Y" and elegant header/footer
    class NumberedCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_elements(num_pages)
                super().showPage()
            super().save()

        def draw_page_elements(self, page_count):
            self.saveState()
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#334155")) # Slate-700

            # Running Header
            self.drawString(54, 752, "CALCULADORA DE SISTEMAS POR UNIDAD (p.u.)")
            self.setFont("Helvetica", 8)
            self.drawRightString(612 - 54, 752, datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
            
            # Header line
            self.setStrokeColor(colors.HexColor("#CBD5E1")) # Slate-300
            self.setLineWidth(0.75)
            self.line(54, 745, 612 - 54, 745)

            # Running Footer
            self.setStrokeColor(colors.HexColor("#E2E8F0")) # Slate-200
            self.setLineWidth(0.5)
            self.line(54, 48, 612 - 54, 48)
            
            self.drawString(54, 34, "Maximiliano Corral Buchhorsts — Valparaíso, Chile — 2026")
            page_text = f"Página {self._pageNumber} de {page_count}"
            self.drawRightString(612 - 54, 34, page_text)
            self.restoreState()

    # In-memory buffer
    pdf_buffer = io.BytesIO()
    
    # 54pt margin represents 0.75 inch. Page size is 612 x 792.
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=72,  # Give room for running header at 745
        bottomMargin=72 # Give room for running footer at 48
    )

    styles = getSampleStyleSheet()
    
    # Modify default styles or add custom ones
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#0F172A"), # Slate-900
        alignment=0, # Left-aligned
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748B"), # Slate-500
        spaceAfter=20
    )

    h1_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#1E293B"), # Slate-800
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )

    th_style = ParagraphStyle(
        "TableHeader",
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white
    )

    td_style = ParagraphStyle(
        "TableCell",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155")
    )

    mono_style = ParagraphStyle(
        "DesgloseMono",
        fontName="Courier",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0F172A")
    )

    story = []

    # Title & Metadata
    story.append(Paragraph(html.escape(req.titulo), title_style))
    story.append(Paragraph(f"Este informe consolida la memoria de cálculo eléctrico acumulada durante la sesión de terreno. Generado automáticamente.", subtitle_style))
    story.append(Spacer(1, 10))

    if not req.historial:
        story.append(Paragraph("No se registraron cálculos en la sesión.", td_style))
    else:
        for idx, item in enumerate(req.historial, start=1):
            story.append(Paragraph(html.escape(f"{idx}. {item.titulo}"), h1_style))
            
            # Build nice summary table of parameters
            table_data = [[Paragraph("Parámetro", th_style), Paragraph("Valor", th_style)]]
            
            # Merge both inputs and outputs in one clear key-value table
            for key, val in item.datos_entrada.items():
                # Format key for humans
                k_clean = str(key).replace("_", " ").title()
                table_data.append([Paragraph(k_clean, td_style), Paragraph(str(val), td_style)])
                
            for key, val in item.datos_salida.items():
                if key != "desglose":
                    k_clean = f"<b>{str(key).replace('_', ' ').title()} (Resultado)</b>"
                    table_data.append([Paragraph(k_clean, td_style), Paragraph(f"<b>{str(val)}</b>", td_style)])
            
            # Format the table
            param_table = Table(table_data, colWidths=[200, 304])
            param_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")), # Slate-800 header
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ('TOPPADDING', (0,0), (-1,-1), 4),
                ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor("#F8FAFC"), colors.white]),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
            ]))
            
            story.append(param_table)
            story.append(Spacer(1, 8))

            # Monospace formula step-by-step block
            desglose_text = "\n".join(item.desglose)
            code_flow = Preformatted(desglose_text, mono_style)
            
            # Wrap code block inside a table cell for a styled card look
            card_table = Table([[code_flow]], colWidths=[504])
            card_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")), # Slate-100 card
                ('BOX', (0,0), (-1,-1), 0.75, colors.HexColor("#E2E8F0")),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 10),
                ('RIGHTPADDING', (0,0), (-1,-1), 10),
            ]))
            
            story.append(card_table)
            story.append(Spacer(1, 15))

    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Reset buffer position
    pdf_buffer.seek(0)
    
    headers = {
        'Content-Disposition': 'attachment; filename="desarrollo_pu.pdf"',
        'Content-Type': 'application/pdf'
    }
    
    return StreamingResponse(pdf_buffer, headers=headers)

from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

# Serve SPA
@app.get("/")
def read_index():
    return FileResponse(BASE_DIR / "templates" / "index.html")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
