"""
Control de Desinfección de Huevo — María Almenara
====================================================

App Streamlit para registrar el control de desinfección de huevo (MA-FR-033),
siguiendo el mismo patrón de las apps PT / PI / Cocina Dulce:
- Carpeta en Drive: "Desinfeccion huevo" (misma raíz que las otras 3 carpetas)
- Spreadsheet mensual: "Septiembre 2026 - Huevo" (ya creado por Kath)
- Cada FECHA crea/usa una hoja (tab) distinta dentro del spreadsheet mensual,
  duplicando la plantilla "Hoja 1" la primera vez que se usa esa fecha.

Campos editables por el usuario: FECHA, TIEMPO (min), EJECUTOR.
Los demás campos del formato quedan FIJOS (constantes abajo) pero se muestran
en pantalla como recordatorio antes de guardar.
"""

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import date

# ──────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN — AJUSTA ESTOS VALORES FIJOS SEGÚN CORRESPONDA
# ──────────────────────────────────────────────────────────────────────────
CARPETA_NOMBRE = "Desinfeccion huevo"          # subcarpeta dentro de ROOT_FOLDER_ID
HOJA_PLANTILLA = "Hoja 1"                       # nombre de la hoja plantilla dentro de cada spreadsheet mensual
FILA_ENCABEZADO = 4                             # fila donde están los títulos de columna (A4:I4)
MARCADOR_PIE = "Se prohíbe la reproducción"     # texto que identifica la fila de pie de página (no tocar)

# Valores fijos del registro (se muestran como recordatorio y se guardan tal cual en cada fila).
# EDITA estos valores si no corresponden exactamente a tu proceso real.
CAMPOS_FIJOS = {
    "LÍNEA": "PROCESOS",
    "PRODUCTO": "Huevo",
    "VºBº JEFE DE CALIDAD": "",
}

OPCIONES_MINUTOS = ["3 minutos", "4 minutos", "5 minutos", "> 5 minutos"]
OPCIONES_LAVADO = ["Conforme", "No conforme"]
OPCIONES_PPM = ["Mayor a 200 ppm", "Menor a 200 ppm"]
COMENTARIO_VACIO = "Sin comentarios correctivos"

# ──────────────────────────────────────────────────────────────────────────
# CONEXIÓN A GOOGLE DRIVE / SHEETS
# ──────────────────────────────────────────────────────────────────────────
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def conectar_gspread():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    return gspread.authorize(creds)


def obtener_carpeta_id(gc, nombre_carpeta, root_folder_id):
    """Busca una subcarpeta por nombre dentro de ROOT_FOLDER_ID."""
    # Usamos el cliente HTTP interno de gspread para consultar la API de Drive v3 directamente
    resp = gc.http_client.request(
        "get",
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": (
                f"'{root_folder_id}' in parents and "
                f"name = '{nombre_carpeta}' and "
                "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            ),
            "fields": "files(id, name)",
        },
    )
    archivos = resp.json().get("files", [])
    if not archivos:
        raise FileNotFoundError(
            f"No se encontró la carpeta '{nombre_carpeta}' dentro de la carpeta raíz. "
            "Verifica el nombre exacto y que la cuenta de servicio tenga acceso."
        )
    return archivos[0]["id"]


def obtener_spreadsheet_mensual(gc, carpeta_id, nombre_spreadsheet):
    """Busca (no crea) el spreadsheet mensual dentro de la carpeta de desinfección de huevo."""
    resp = gc.http_client.request(
        "get",
        "https://www.googleapis.com/drive/v3/files",
        params={
            "q": (
                f"'{carpeta_id}' in parents and "
                f"name = '{nombre_spreadsheet}' and "
                "mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
            ),
            "fields": "files(id, name)",
        },
    )
    archivos = resp.json().get("files", [])
    if not archivos:
        raise FileNotFoundError(
            f"No se encontró el spreadsheet '{nombre_spreadsheet}' dentro de la carpeta "
            f"'{CARPETA_NOMBRE}'. Confirma que el nombre coincide exactamente."
        )
    return gc.open_by_key(archivos[0]["id"])


def nombre_spreadsheet_mensual(fecha: date) -> str:
    meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
    }
    return f"{meses[fecha.month]} {fecha.year} - Huevo"


def obtener_o_crear_hoja_del_dia(spreadsheet, fecha: date):
    """Devuelve la worksheet (tab) correspondiente a la fecha, duplicando la plantilla si no existe."""
    nombre_tab = fecha.strftime("%Y-%m-%d")
    try:
        return spreadsheet.worksheet(nombre_tab)
    except gspread.WorksheetNotFound:
        plantilla = spreadsheet.worksheet(HOJA_PLANTILLA)
        nueva = plantilla.duplicate(new_sheet_name=nombre_tab)
        return nueva


def encontrar_fila_insercion(worksheet):
    """
    Encuentra la fila justo antes del pie de página (MARCADOR_PIE) para insertar
    el nuevo registro arriba de él, igual que en las apps PT / PI / Cocina Dulce.
    Si no encuentra el marcador, inserta después de la última fila con datos.
    """
    valores_col_a = worksheet.col_values(1)
    for idx, valor in enumerate(valores_col_a, start=1):
        if MARCADOR_PIE in (valor or ""):
            return idx
    # Fallback: al final de la hoja
    return len(worksheet.get_all_values()) + 1


def guardar_registro(worksheet, fecha, lavado, ppm, minutos, accion_correctiva, ejecutor):
    fila_insercion = encontrar_fila_insercion(worksheet)
    nueva_fila = [
        fecha.strftime("%d/%m/%Y"),
        CAMPOS_FIJOS["LÍNEA"],
        CAMPOS_FIJOS["PRODUCTO"],
        lavado,
        ppm,
        minutos,
        accion_correctiva,
        ejecutor,
        CAMPOS_FIJOS["VºBº JEFE DE CALIDAD"],
    ]
    worksheet.insert_row(nueva_fila, index=fila_insercion, value_input_option="USER_ENTERED")


# ──────────────────────────────────────────────────────────────────────────
# INTERFAZ STREAMLIT
# ──────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Control Desinfección Huevo", page_icon="🥚", layout="centered")

st.title("🥚 Control de Desinfección de Huevo")
st.caption("MA-FR-033 · Control de procesos · María Almenara")

with st.expander("ℹ️ Recordatorio del proceso", expanded=True):
    st.markdown(
        f"""
        - **Línea:** {CAMPOS_FIJOS['LÍNEA']}
        - **Producto:** {CAMPOS_FIJOS['PRODUCTO']}
        - **Solución:** hipoclorito de sodio
        - **Concentración mínima:** > 200 ppm — **tiempo mínimo:** 5 min
        - Si la concentración es inferior al LC: preparar nuevamente la solución y desinfectar de nuevo.
        - Si el tiempo fue inferior al LC: enjuagar y desinfectar nuevamente.
        """
    )

st.divider()
st.subheader("Nuevo registro")

fecha_seleccionada = st.date_input("Fecha", value=date.today(), format="DD/MM/YYYY")
lavado = st.selectbox("Lavado", options=OPCIONES_LAVADO)
ppm = st.selectbox("Desinfección [ ] ppm", options=OPCIONES_PPM)
minutos = st.selectbox("Tiempo de desinfección (min)", options=OPCIONES_MINUTOS)

dejar_sin_comentario = st.checkbox("Dejar acción correctiva vacía", value=True)
if dejar_sin_comentario:
    accion_correctiva = COMENTARIO_VACIO
    st.caption(f"Se guardará como: “{COMENTARIO_VACIO}”")
else:
    accion_correctiva = st.text_area("Comentario de acción correctiva", placeholder="Escribe el comentario...")

ejecutor = st.text_input("Ejecutor (Supervisor de Calidad)", placeholder="Nombre completo")

st.divider()

if st.button("💾 Guardar registro", type="primary", use_container_width=True):
    if not ejecutor.strip():
        st.error("Por favor ingresa el nombre del ejecutor antes de guardar.")
    elif not dejar_sin_comentario and not accion_correctiva.strip():
        st.error("Escribe un comentario de acción correctiva o marca la casilla para dejarlo vacío.")
    else:
        accion_final = accion_correctiva if dejar_sin_comentario else accion_correctiva.strip()
        try:
            with st.spinner("Guardando en Google Sheets..."):
                gc = conectar_gspread()
                root_folder_id = st.secrets["ROOT_FOLDER_ID"]
                carpeta_id = obtener_carpeta_id(gc, CARPETA_NOMBRE, root_folder_id)
                nombre_ss = nombre_spreadsheet_mensual(fecha_seleccionada)
                spreadsheet = obtener_spreadsheet_mensual(gc, carpeta_id, nombre_ss)
                worksheet = obtener_o_crear_hoja_del_dia(spreadsheet, fecha_seleccionada)
                guardar_registro(
                    worksheet, fecha_seleccionada, lavado, ppm, minutos, accion_final, ejecutor.strip()
                )
            st.success(
                f"✅ Registro guardado correctamente en '{nombre_ss}' → "
                f"hoja '{fecha_seleccionada.strftime('%Y-%m-%d')}'."
            )
            st.balloons()
        except FileNotFoundError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Ocurrió un error al guardar: {e}")
