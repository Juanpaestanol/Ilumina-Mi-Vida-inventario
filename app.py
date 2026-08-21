import base64
import hashlib
import io
import threading
from datetime import datetime
import time

def get_session_token(username: str) -> str:
    secret_salt = "ilumina_mi_vida_secret_salt_2026"
    return hashlib.sha256(f"{username}:{secret_salt}".encode("utf-8")).hexdigest()

import pandas as pd
import streamlit as st

from src.services.database import Database
from src.services.export_service import ExportService
from src.services.inventory_service import InventoryService
from src.utils.image_utils import process_image

# ---- Page Configuration & Styles ----
st.set_page_config(
    page_title="Ilumina mi vida - Inventario", page_icon=":material/brightness_high:", layout="wide"
)

# ---- Inject Custom Premium CSS (Orange/Gold theme) ----
st.markdown(
    """
<style>
    @import url('https://fonts.google.com/specimen/Roboto+Slab');
    .banner-title {
    font-family: 'Roboto Slab', sans-serif;
    }
    /* Main container background and styling */
    .stApp {
        background-color: #faf0e6;
    }
    
    /* Hide Deploy button */
    .stAppDeployButton {
        visibility: hidden;
    }
    
    /* Header Banner Styling */
    .header-container {
        background: linear-gradient(135deg, #e68a2e 0%, #3d2b1a 100%);
        padding: 2.5rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.15);
        text-align: center;
    }
    .header-title {
        font-family: 'Roboto Slab', 'Ubuntu', sans-serif;
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: 1px;
    }
    .header-subtitle {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    
    /* Card Styles */
    .item-card {
        background: white;
        padding: 1.2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border: 1px solid #e8c9b0;
        margin-bottom: 1rem;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .item-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(230, 138, 46, 0.15);
    }
    
    /* Metric styling */
    .metric-box {
        background: #f5dcc8;
        padding: 1rem;
        border-radius: 8px;
        border-left: 5px solid #e68a2e;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: bold;
        color: #3d2b1a;
    }
    .metric-label {
        font-size: 0.9rem;
        color: #6d5b4a;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---- Cache Database Connection & Lock ----
@st.cache_resource
def get_db() -> Database:
    db = Database()
    db.initialize()
    return db


@st.cache_resource
def get_db_lock() -> threading.Lock:
    return threading.Lock()


db = get_db()
db_lock = get_db_lock()

# ---- Authentication State ----
if "logged_in" not in st.session_state:
    user_param = st.query_params.get("user")
    token_param = st.query_params.get("session_token")
    if user_param and token_param and token_param == get_session_token(user_param):
        st.session_state.logged_in = True
        st.session_state.username = user_param
    else:
        st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# ---- Login Screen ----
if not st.session_state.logged_in:
    st.markdown(
        """
        <div class="header-container">
            <h1 class="header-title"> Acceso al Sistema</h1>
            <p class="header-subtitle">Ilumina Mi Vida - Control de Inventario</p>
        </div>
    """,
        unsafe_allow_html=True,
    )

    col_login_left, col_login_mid, col_login_right = st.columns([1, 1.5, 1])
    with col_login_mid:
        with st.form("login_form"):
            user = st.text_input("Usuario:").strip().upper()
            password = st.text_input("Contraseña:", type="password")
            submit = st.form_submit_button("Entrar", width="stretch")

            if submit:
                if password == "Ilumina916" and user:
                    with db_lock:
                        st.session_state.logged_in = True
                        st.session_state.username = user
                        st.query_params["user"] = user
                        st.query_params["session_token"] = get_session_token(user)
                        # Initialize service & log login
                        service = InventoryService(db.connection, user)
                        service.log_event(
                            "INICIO_SESION", f"Usuario {user} inició sesión", "SEGURIDAD", "N/A"
                        )
                    st.rerun()
                else:
                    with db_lock:
                        temp_service = InventoryService(db.connection, user or "ANONIMO")
                        temp_service.log_event(
                            "INICIO_SESION_FALLIDO",
                            f"Intento de inicio de sesión fallido para el usuario: {user or 'ANONIMO'}",
                            "SEGURIDAD",
                            "N/A"
                        )
                    st.error("Usuario o contraseña incorrectos.")
    st.stop()

# ---- Logged-in Header & Session ----
username = st.session_state.username
service = InventoryService(db.connection, username)


# User Panel & Logout Row
col_info, col_logout = st.columns([5, 1])
with col_info:
    st.write(f":material/calendar_today: **Fecha de operación:** {datetime.now().strftime('%d/%m/%Y')}")
with col_logout:
    if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
        with db_lock:
            service.log_event(
                "CIERRE_SESION", f"Usuario {username} cerró sesión", "SEGURIDAD", "N/A"
            )
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.query_params.clear()
        st.rerun()

# Header Banner
st.markdown(
    f"""
    <div class="header-container">
        <h1 class="header-title">Ilumina Mi Vida</h1>
        <p class="header-subtitle">Gestión de inventario | Usuario: <b>{username}</b></p>
    </div>
""",
    unsafe_allow_html=True,
)


# Tabs
tab_inv, tab_mov, tab_mat_lug, tab_hist, tab_rep, tab_inst = st.tabs(
    [
        ":material/inventory: Inventario",
        ":material/swap_horiz: Movimientos",
        ":material/build: Materiales y lugares",
        ":material/history: Historial y auditoría",
        ":material/analytics: Reportes Excel",
        ":material/help: Instructivo",
    ],
    on_change="rerun",
    key="active_tab",
)

# ----------------------------------------------------
# TAB 1: INVENTARIO
# ----------------------------------------------------
if tab_inv.open:
    with tab_inv:
        st.subheader("Filtros de búsqueda")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            search_code = (
                st.text_input("Código de pulsera:", placeholder="Buscar por código...")
                .strip()
                .upper()
            )
        with col_f2:
            mats = service.get_materials()
            mat_options = ["Todos"] + [m["Name"] for m in mats]
            search_mat = st.selectbox("Material:", mat_options)
        with col_f3:
            search_desc = st.text_input(
                "Descripción:", placeholder="Buscar por descripción..."
            ).strip()

        # Load all items from DB
        with db_lock:
            items = service.get_all_items()

        # Filter items
        filtered_items = []
        for item in items:
            if search_code and search_code not in item["Id"].upper():
                continue
            if search_mat != "Todos" and item["MaterialName"] != search_mat:
                continue
            if (
                search_desc
                and search_desc.lower() not in (item["Description"] or "").lower()
            ):
                continue
            filtered_items.append(item)

        # Actions: Nueva Pulsera
        @st.dialog("Agregar nueva pulsera")
        def add_item_dialog():
            with st.form("add_item_form", clear_on_submit=True):
                item_id = st.text_input("Código de pulsera:").strip().upper()

                # Material Dropdown
                m_options = {m["Name"]: m["Id"] for m in mats}
                mat_name = st.selectbox("Material:", list(m_options.keys()))
                material_id = m_options[mat_name]

                description = st.text_input("Descripción / detalles:")
                price = st.number_input(
                    "Precio ($):", min_value=0.0, step=1.0, format="%.2f"
                )
                stock = st.number_input("Stock inicial:", min_value=0, step=1)
                date_str = st.text_input(
                    "Fecha de alta (YYYY-MM-DD):", value=datetime.now().strftime("%Y-%m-%d")
                )

                uploaded_file = st.file_uploader(
                    "Subir imagen (opcional):", type=["jpg", "jpeg", "png"]
                )

                submit_btn = st.form_submit_button(
                    "Guardar pulsera", icon=":material/save:", width="stretch"
                )
                if submit_btn:
                    if not item_id:
                        st.error("El código es obligatorio.")
                        return

                    # Image processing
                    large_data = None
                    thumb_data = None
                    if uploaded_file:
                        raw_img = uploaded_file.read()
                        try:
                            large_data = raw_img
                            thumb_data = process_image(raw_img, 280)
                        except Exception as e:
                            st.error(f"Error al procesar la imagen: {e}")
                            return

                    item_data = {
                        "Id": item_id,
                        "MaterialId": material_id,
                        "Description": description,
                        "Price": price,
                        "Stock": stock,
                        "CreatedDate": date_str,
                        "ImageData": large_data,
                        "ThumbnailData": thumb_data,
                    }

                    with db_lock:
                        success = service.add_item(item_data)
                    if success:
                        st.success(f"Pulsera {item_id} agregada exitosamente.")
                        st.rerun()
                    else:
                        st.error("El código de la pulsera ya existe en la base de datos.")

        # Edit Item Dialog
        @st.dialog("Editar pulsera")
        def edit_item_dialog(item_to_edit):
            with st.form("edit_item_form"):
                st.write(f"Editando código: **{item_to_edit['Id']}**")

                # Material Dropdown
                m_options = {m["Name"]: m["Id"] for m in mats}
                default_mat_name = item_to_edit.get(
                    "MaterialName", next(iter(m_options.keys())) if m_options else ""
                )
                mat_names_list = list(m_options.keys())
                try:
                    def_idx = mat_names_list.index(default_mat_name)
                except ValueError:
                    def_idx = 0

                mat_name = st.selectbox("Material:", mat_names_list, index=def_idx)
                material_id = m_options[mat_name]

                description = st.text_input(
                    "Descripción / detalles:", value=item_to_edit.get("Description", "")
                )
                price = st.number_input(
                    "Precio ($):",
                    min_value=0.0,
                    step=1.0,
                    value=float(item_to_edit.get("Price", 0.0)),
                    format="%.2f",
                )
                stock = st.number_input(
                    "Stock:", min_value=0, step=1, value=int(item_to_edit.get("Stock", 0))
                )
                date_str = st.text_input(
                    "Fecha de alta (YYYY-MM-DD):",
                    value=item_to_edit.get(
                        "CreatedDate", datetime.now().strftime("%Y-%m-%d")
                    ),
                )

                # Image Preview & Uploader
                current_image = item_to_edit.get("ImageData") or item_to_edit.get(
                    "ThumbnailData"
                )
                if current_image:
                    st.image(current_image, caption="Imagen actual", width=120)

                uploaded_file = st.file_uploader(
                    "Actualizar imagen (opcional):", type=["jpg", "jpeg", "png"]
                )

                edit_reason = st.text_input(
                    "Motivo de la edición (obligatorio):", placeholder="Ej: Ajuste de stock, actualización de precio, etc."
                ).strip()

                submit_btn = st.form_submit_button(
                    "Guardar cambios", icon=":material/save:", width="stretch"
                )
                if submit_btn:
                    if not edit_reason:
                        st.error("El motivo de la edición es obligatorio.")
                        return

                    large_data = item_to_edit.get("ImageData")
                    thumb_data = item_to_edit.get("ThumbnailData")

                    if uploaded_file:
                        raw_img = uploaded_file.read()
                        try:
                            large_data = raw_img
                            thumb_data = process_image(raw_img, 280)
                        except Exception as e:
                            st.error(f"Error al procesar la imagen: {e}")
                            return

                    updated_data = {
                        "MaterialId": material_id,
                        "Description": description,
                        "Price": price,
                        "Stock": stock,
                        "CreatedDate": date_str,
                        "ImageData": large_data,
                        "ThumbnailData": thumb_data,
                    }

                    with db_lock:
                        success = service.update_item(item_to_edit["Id"], updated_data, edit_reason)
                    if success:
                        st.success("Cambios guardados exitosamente.")
                        st.rerun()
                    else:
                        st.error("Error al actualizar la pulsera.")

        # Details Dialog
        @st.dialog("Detalles de pulsera")
        def details_dialog(item_to_view):
            col_det_img, col_det_text = st.columns([1, 1])
            with col_det_img:
                # Try full image first, fall back to thumbnail
                full_img_data = item_to_view.get("ImageData") or item_to_view.get(
                    "ThumbnailData"
                )
                if full_img_data:
                    st.image(full_img_data, width="stretch")
                else:
                    st.info("Sin imagen disponible")
            with col_det_text:
                st.write(f"**Código:** `{item_to_view['Id']}`")
                st.write(f"**Material:** {item_to_view.get('MaterialName', '')}")
                st.write(f"**Descripción:** {item_to_view.get('Description', '')}")
                st.write(f"**Precio:** ${item_to_view['Price']:.2f}")
                st.write(f"**Stock:** {item_to_view['Stock']} piezas")
                st.write(f"**Total Vendidos:** {item_to_view['TotalSold']} unidades")
                st.write(f"**Fecha de Alta:** {item_to_view['CreatedDate']}")
                st.write(
                    f"**Estado:** {'Eliminado' if item_to_view.get('Deleted') else 'Activo'}"
                )

        # Add new button
        if st.button("Registrar nueva pulsera", icon=":material/add:", type="primary"):
            add_item_dialog()

        st.write("")

        # Display items in split-screen layout
        if not filtered_items:
            st.info("No se encontraron pulseras que coincidan con los filtros.")
        else:
            col_list, col_detail = st.columns([1.8, 1.2])

            with col_list:
                st.subheader("Modelos en inventario")
                
                # Create display dataframe with inline base64 thumbnails
                df_list = []
                for item in filtered_items:
                    img_uri = None
                    if item.get("ThumbnailData"):
                        try:
                            # Convert raw thumbnail bytes to base64 Data URI
                            b64_str = base64.b64encode(item["ThumbnailData"]).decode("utf-8")
                            img_uri = f"data:image/jpeg;base64,{b64_str}"
                        except Exception:
                            pass
                    
                    df_list.append({
                        "Vista Previa": img_uri,
                        "Código": item["Id"],
                        "Material": item["MaterialName"],
                        "Descripción": item["Description"] or "-",
                        "Precio ($)": item["Price"],
                        "Stock": item["Stock"],
                        "Vendidos": item["TotalSold"]
                    })
                
                df_display = pd.DataFrame(df_list)

                column_config = {
                    "Vista Previa": st.column_config.ImageColumn("Vista Previa", width="small"),
                    "Código": st.column_config.TextColumn("Código", help="Código único de la pulsera"),
                    "Material": st.column_config.TextColumn("Material"),
                    "Descripción": st.column_config.TextColumn("Descripción"),
                    "Precio ($)": st.column_config.NumberColumn("Precio", format="$%.2f"),
                    "Stock": st.column_config.NumberColumn("Stock"),
                    "Vendidos": st.column_config.NumberColumn("Vendidos")
                }

                event = st.dataframe(
                    df_display,
                    column_config=column_config,
                    hide_index=True,
                    on_select="rerun",
                    #selection_mode=["single-row", "single-cell"],
                    selection_mode="single-cell",
                    key="items_table"
                )

            with col_detail:
                st.subheader("Detalles del modelo")
                
                selected_cells = event.selection.get("cells", [])
                selected_idx = None
                if selected_cells:
                    cell = selected_cells[0]
                    selected_idx = cell.get("row") if isinstance(cell, dict) else cell[0]
                                
                if selected_idx is not None and selected_idx < len(filtered_items):
                    selected_item = filtered_items[selected_idx]
        
                    with db_lock:
                        full_item = service.get_item(selected_item["Id"])
        
                    if full_item:
                        with st.container(border=True):
                            img_to_show = full_item.get("ImageData") or full_item.get("ThumbnailData")
                            if img_to_show:
                                st.image(img_to_show, width="stretch")
                            else:
                                st.info("Sin imagen disponible")                
                            st.write(f"### `{full_item['Id']}`")
                            st.write(f"**Material:** {full_item.get('MaterialName', '')}")
                            st.write(f"**Descripción:** {full_item.get('Description') or 'Sin descripción'}")
                
                            m_col1, m_col2 = st.columns(2)
                            with m_col1:
                                st.metric("Precio", f"${full_item['Price']:.2f}")
                                st.metric("Stock", f"{full_item['Stock']} pzs")
                            with m_col2:
                                st.metric("Vendidos", f"{full_item['TotalSold']} unds")
                                if "Ganancias" in full_item:
                                    st.metric("Ganancias", f"${full_item['Ganancias']:.2f}")
                                else:
                                    st.metric("Ganancias", f"${(full_item['Price'] * full_item['TotalSold']):.2f}")
                
                            st.write(f"*Fecha de alta:* {full_item['CreatedDate']}")
                
                            st.write("---")
                            act_col1, act_col2 = st.columns(2)
                            with act_col1:
                                if st.button(
                                    "Editar pulsera",
                                    icon=":material/edit:",
                                    key="detail_btn_edit",
                                    type="primary",
                                    width="stretch"
                                ):
                                    edit_item_dialog(full_item)
                            with act_col2:
                                if st.button(
                                    "Eliminar pulsera",
                                    icon=":material/delete:",
                                    key="detail_btn_delete",
                                    type="secondary",
                                    width="stretch"
                                ):
                                    st.session_state[f"confirm_del_detail_{full_item['Id']}"] = True
                
                            if st.session_state.get(f"confirm_del_detail_{full_item['Id']}"):
                                with st.container():
                                    st.warning(f"¿Confirma eliminar '{full_item['Id']}'?")
                                    conf_c1, conf_c2 = st.columns(2)
                                    with conf_c1:
                                        if st.button("Sí, eliminar", type="primary", key="confirm_yes_del", width="stretch"):
                                            with db_lock:
                                                success = service.delete_item(full_item["Id"])
                                            if success:
                                                st.toast(f"Pulsera {full_item['Id']} eliminada.")
                                                del st.session_state[f"confirm_del_detail_{full_item['Id']}"]
                                                st.rerun()
                                            else:
                                                st.error("No se pudo eliminar la pulsera.")
                                    with conf_c2:
                                        if st.button("Cancelar", key="confirm_no_del", width="stretch"):
                                            del st.session_state[f"confirm_del_detail_{full_item['Id']}"]
                                            st.rerun()
                else:
                    st.info("Seleccione una celda de la tabla para ver sus detalles.")

# ----------------------------------------------------
# TAB 2: MOVIMIENTOS
# ----------------------------------------------------
if tab_mov.open:
    with tab_mov:
        st.subheader("Registrar movimiento de inventario")
        if "tipo_movimiento" not in st.session_state:
            st.session_state.tipo_movimiento = "Venta"
        st.write("Seleccione el tipo de movimiento:")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button(
                "🛒 Venta",
                use_container_width=True,
                type="primary" if st.session_state.tipo_movimiento == "Venta" else "secondary",
            ):
                st.session_state.tipo_movimiento = "Venta"
                st.rerun()
        with c2:
            if st.button(
                "📦 Resurtido",
                use_container_width=True,
                type="primary" if st.session_state.tipo_movimiento == "Resurtido" else "secondary",
            ):
                st.session_state.tipo_movimiento = "Resurtido"
                st.rerun()
        with c3:
            if st.button(
                "🎁 Regalo",
                use_container_width=True,
                type="primary" if st.session_state.tipo_movimiento == "Regalo" else "secondary",
            ):
                st.session_state.tipo_movimiento = "Regalo"
                st.rerun()
        with c4:
            if st.button(
                "⚠️ Pérdida",
                use_container_width=True,
                type="primary" if st.session_state.tipo_movimiento == "Pérdida" else "secondary",
            ):
                st.session_state.tipo_movimiento = "Pérdida"
                st.rerun()
        mov_type = st.session_state.tipo_movimiento

        # Load items list for select box
        with db_lock:
            all_items_db = service.get_all_items()

        if not all_items_db:
            st.warning(
                "No hay pulseras en el inventario. Registre una primero en la pestaña de Inventario."
            )
        else:
            with st.form("movement_form", clear_on_submit=True):
                item_labels = {
                    f"{it['Id']} - {it['Description']} (Stock: {it['Stock']})": it["Id"]
                    for it in all_items_db
                }
                selected_label = st.selectbox(
                    "Pulsera:",
                    options=list(item_labels.keys()),
                    index=None,
                    placeholder="Seleccione o busque una pulsera...",
                )
                selected_item_id = item_labels.get(selected_label) if selected_label else None

                qty = st.number_input("Cantidad:", min_value=1, value=1, step=1)
                date_str = st.text_input(
                    "Fecha (YYYY-MM-DD):", value=datetime.now().strftime("%Y-%m-%d")
                )

                # Action-specific inputs
                location_id = None
                note = ""
                if mov_type == "Venta":
                    with db_lock:
                        locs = service.get_locations()
                    loc_labels = {f"{loc['Id']} - {loc['Name']}": loc["Id"] for loc in locs}
                    if not loc_labels:
                        st.error(
                            "No hay lugares registrados. Registre un lugar primero en la pestaña Materiales & Lugares."
                        )
                        st.stop()
                    selected_loc_label = st.selectbox(
                        "Lugar de venta:", list(loc_labels.keys())
                    )
                    location_id = loc_labels[selected_loc_label]
                    note = st.text_input("Nota / comprobante (opcional):")
                elif mov_type == "Resurtido":
                    note = st.text_input("Nota / detalle del resurtido (opcional):")
                elif mov_type == "Regalo":
                    note = st.text_input("Persona o motivo del regalo (obligatorio):")
                elif mov_type == "Pérdida":
                    loss_reason = st.segmented_control(
                        "Motivo de pérdida:",
                        ["Robo", "Pérdida"],
                        default="Robo",
                        required=True,
                    )
                    note = loss_reason

                confirm_btn = st.form_submit_button(
                    "Confirmar movimiento", icon=":material/check:", width="stretch"
                )
                if confirm_btn:
                    success = False
                    with db_lock:
                        if mov_type == "Venta":
                            if location_id:
                                success = service.register_sale(
                                    selected_item_id, location_id, qty, date_str, note
                                )
                            else:
                                st.error("Debe seleccionar un lugar de venta.")
                        elif mov_type == "Resurtido":
                            success = service.register_restock(
                                selected_item_id, qty, date_str, note
                            )
                        elif mov_type == "Regalo":
                            if not note:
                                st.error(
                                    "Debe ingresar un motivo o persona para registrar el regalo."
                                )
                            else:
                                success = service.register_gift(
                                    selected_item_id, note, qty, date_str
                                )
                        elif mov_type == "Pérdida":
                            success = service.register_loss(
                                selected_item_id, note, qty, date_str
                            )

                    if success:
                        st.success(f"Movimiento '{mov_type}' registrado exitosamente.")
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error(
                            "Error al registrar movimiento. Verifique que el stock sea suficiente."
                        )

# ----------------------------------------------------
# TAB 3: MATERIALES & LUGARES
# ----------------------------------------------------
if tab_mat_lug.open:
    with tab_mat_lug:
        col_mat, col_sep, col_lug = st.columns([1, 0.08, 1])

        # Left column: Materials
        with col_mat:
            st.subheader("Clasificación de materiales")

            # Add material form
            with st.form("add_material_form", clear_on_submit=True):
                new_mat_name = st.text_input("Nombre de material nuevo:").strip()
                add_mat_btn = st.form_submit_button("Agregar material", icon=":material/add:")
                if add_mat_btn:
                    if new_mat_name:
                        with db_lock:
                            success = service.add_material(new_mat_name.capitalize())
                        if success:
                            st.success("Material agregado exitosamente.")
                            st.rerun()
                        else:
                            st.error("El material ya existe.")
                    else:
                        st.error("El nombre del material es obligatorio.")

            # Display and Delete Materials
            with db_lock:
                materials_list = service.get_materials()

            if not materials_list:
                st.info("No hay materiales registrados.")
            else:
                df_mats = pd.DataFrame(materials_list)
                event_mat = st.dataframe(
                    df_mats,
                    hide_index=True,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-cell",
                    key="table_mats",
                    column_config={
                        "Id": st.column_config.Column("Id", width="small"),
                        "Name": st.column_config.Column("Nombre", width="large"),
                    },
                )

                selected_mat_cells = event_mat.selection.get("cells", [])
                selected_mat_idx = None
                if selected_mat_cells:
                    cell = selected_mat_cells[0]
                    selected_mat_idx = cell.get("row") if isinstance(cell, dict) else cell[0]

                if selected_mat_idx is not None and selected_mat_idx < len(materials_list):
                    selected_mat = materials_list[selected_mat_idx]
                
                    with st.form("manage_material_form"):
                        st.markdown(f"**Administrar:** {selected_mat['Name']}")
                        updated_mat_name = st.text_input(
                            "Material seleccionado:", value=selected_mat["Name"]
                        ).strip()

                        col_b1, col_b2 = st.columns(2)
                        with col_b1:
                            edit_mat_btn = st.form_submit_button(
                                "Editar material", icon=":material/edit:", use_container_width=True
                            )
                        with col_b2:
                            del_mat_btn = st.form_submit_button(
                                "Eliminar material", icon=":material/delete:", use_container_width=True
                            )

                        if edit_mat_btn:
                            if updated_mat_name:
                                with db_lock:
                                    success = service.edit_material(
                                        selected_mat["Id"], updated_mat_name.capitalize()
                                    )
                                if success:
                                    st.success("Material actualizado exitosamente.")
                                    st.rerun()
                                else:
                                    st.error("No se pudo actualizar o el nombre ya existe.")
                            else:
                                st.error("El nombre no puede estar vacío.")

                        if del_mat_btn:
                            with db_lock:
                                success = service.delete_material(selected_mat["Id"])
                            if success:
                                st.success("Material eliminado (archivado).")
                                st.rerun()
                            else:
                                st.error("No se pudo eliminar el material.")
                else:
                    st.caption("Haz clic en cualquier fila de la tabla para editar o eliminar un material.")

                # Restore selection
                with db_lock:
                    deleted_materials = [m for m in service.get_materials(include_deleted=True) if m.get("Deleted") == 1]
                if deleted_materials:
                    with st.form("restore_material_form"):
                        mat_res_options = {m["Name"]: m["Id"] for m in deleted_materials}
                        selected_mat_res = st.selectbox(
                            "Seleccionar material a restaurar:", list(mat_res_options.keys())
                        )
                        res_mat_btn = st.form_submit_button("Restaurar material seleccionado", icon=":material/restore:")
                        if res_mat_btn:
                            mat_id_to_res = mat_res_options[selected_mat_res]
                            with db_lock:
                                success = service.restore_material(mat_id_to_res)
                            if success:
                                st.success("Material restaurado.")
                                st.rerun()
                            else:
                                st.error("No se pudo restaurar el material.")

        with col_sep:
            st.markdown(
                """
                <div style="
                    border-left: 2px solid #d4b896;
                    height: 90%;
                    min-height: 750px;
                    margin: 0 auto;
                    width: 1px;
                    opacity: 0.6;
                "></div>
                """,
                unsafe_allow_html=True,
            )

        # Right column: Locations
        with col_lug:
            st.subheader("Lugares de venta")

            # Add location form
            with st.form("add_location_form", clear_on_submit=True):
                new_loc_id = st.text_input("Código de lugar (4 letras):").strip().upper()
                new_loc_name = st.text_input("Nombre completo de lugar:").strip()
                add_loc_btn = st.form_submit_button("Agregar lugar", icon=":material/add:")
                if add_loc_btn:
                    if len(new_loc_id) != 4 or not new_loc_id.isalpha():
                        st.error(
                            "El código del lugar debe constar de exactamente 4 letras."
                        )
                    elif not new_loc_name:
                        st.error("El nombre completo del lugar es obligatorio.")
                    else:
                        with db_lock:
                            success = service.add_location(new_loc_id, new_loc_name)
                        if success:
                            st.success("Lugar agregado exitosamente.")
                            st.rerun()
                        else:
                            st.error("El código del lugar ya existe.")

            # Display and Manage Locations
            with db_lock:
                locations_list = service.get_locations()

            if not locations_list:
                st.info("No hay lugares de venta registrados.")
            else:
                df_locs = pd.DataFrame(locations_list)
                event_loc = st.dataframe(
                    df_locs,
                    hide_index=True,
                    use_container_width=True,
                    on_select="rerun",
                    selection_mode="single-cell",
                    key="table_locs",
                    column_config={
                        "Id": st.column_config.Column("Id", width="small"),
                        "Name": st.column_config.Column("Nombre", width="large"),
                    },
                )

                selected_loc_cells = event_loc.selection.get("cells", [])
                selected_loc_idx = None
                if selected_loc_cells:
                    cell = selected_loc_cells[0]
                    selected_loc_idx = cell.get("row") if isinstance(cell, dict) else cell[0]

                if selected_loc_idx is not None and selected_loc_idx < len(locations_list):
                    selected_loc = locations_list[selected_loc_idx]
                
                    with st.form("manage_location_form"):
                        st.markdown(f"**Administrar:** {selected_loc['Name']} (Código: {selected_loc['Id']})")
                        col_id_edit, col_name_edit = st.columns(2)
                        with col_id_edit:
                            updated_loc_id = st.text_input(
                                "Nuevo código (4 letras):", value=selected_loc["Id"]
                            ).strip().upper()
                        with col_name_edit:
                            updated_loc_name = st.text_input(
                                "Nuevo nombre completo:", value=selected_loc["Name"]
                            ).strip()
                        col_lb1, col_lb2 = st.columns(2)
                        with col_lb1:
                            edit_loc_btn = st.form_submit_button(
                                "Editar lugar", icon=":material/edit:", use_container_width=True
                            )
                        with col_lb2:
                            del_loc_btn = st.form_submit_button(
                                "Eliminar lugar", icon=":material/delete:", use_container_width=True
                            )
                        if edit_loc_btn:
                            if len(updated_loc_id) != 4 or not updated_loc_id.isalpha():
                                st.error("El código del lugar debe constar de exactamente 4 letras.")
                            elif not updated_loc_name:
                                st.error("El nombre completo es obligatorio.")
                            else:
                                with db_lock:
                                    success = service.edit_location(
                                        selected_loc["Id"], updated_loc_id, updated_loc_name
                                    )
                                if success:
                                    st.success("Lugar actualizado exitosamente.")
                                    st.rerun()
                                else:
                                    st.error("Error al actualizar. Verifique que el nuevo código no esté duplicado.")
                        if del_loc_btn:
                            with db_lock:
                                success = service.delete_location(selected_loc["Id"])
                            if success:
                                st.success("Lugar eliminado (archivado).")
                                st.rerun()
                            else:
                                st.error("No se pudo eliminar el lugar.")
                else:
                    st.caption("Haz clic en cualquier celda o fila de la tabla para editar o eliminar un lugar.")

                # Restore location
                with db_lock:
                    deleted_locations = [
                        loc for loc in service.get_locations(include_deleted=True) if loc.get("Deleted") == 1
                    ]
                if deleted_locations:
                    with st.form("restore_location_form"):
                        loc_res_options = {
                            f"{loc['Id']} - {loc['Name']}": loc["Id"] for loc in deleted_locations
                        }
                        selected_loc_res = st.selectbox(
                            "Seleccionar lugar a restaurar:", list(loc_res_options.keys())
                        )
                        res_loc_btn = st.form_submit_button("Restaurar lugar seleccionado", icon=":material/restore:")
                        if res_loc_btn:
                            loc_id_to_res = loc_res_options[selected_loc_res]
                            with db_lock:
                                success = service.restore_location(loc_id_to_res)
                            if success:
                                st.success("Lugar restaurado.")
                                st.rerun()
                            else:
                                st.error("No se pudo restaurar el lugar.")

# ----------------------------------------------------
# TAB 4: HISTORIAL & AUDITORÍA
# ----------------------------------------------------
if tab_hist.open:
    with tab_hist:
        st.subheader("Auditoría de historial de transacciones")
        
        # Load full history
        with db_lock:
            history_list = service.get_history()
            integrity_result = service.verify_log_integrity()

        # Display integrity status shield
        if integrity_result["status"]:
            st.success("Historial íntegro (0 alteraciones detectadas)", icon=":material/shield:")
        else:
            st.error(
                f"¡ATENCIÓN! Se detectó alteración en el registro de auditoría. Filas alteradas: {integrity_result['tampered_ids']}",
                icon=":material/warning:"
            )

        st.info(
            "Nota: Las transacciones originales corregidas se muestran marcadas, pero se conservan para auditoría y trazabilidad completa."
        )

        # Single-Item Timeline Search
        st.write("### Buscar historial de pulsera")
        search_item_id = st.text_input(
            "Ingrese código de pulsera para ver su línea de tiempo de auditoría:",
            placeholder="Ej: PUL-001"
        ).strip().upper()
        
        if search_item_id:
            # Filter history list for this item
            item_history = [
                h for h in history_list 
                if h["TargetType"] == "PULSERA" and h["TargetId"].upper() == search_item_id
            ]
            
            if not item_history:
                st.info(f"No se encontró historial para la pulsera '{search_item_id}'.")
            else:
                st.write(f"#### Línea de tiempo para `{search_item_id}`")
                
                # Order chronological (oldest first)
                item_history_sorted = sorted(item_history, key=lambda x: x["Id"])
                
                for h in item_history_sorted:
                    action = h["ActionType"]
                    user = h["User"]
                    ts = h["Timestamp"]
                    note = h["Note"] or "-"
                    qty = f" (Cantidad: {h['Quantity']})" if h["Quantity"] is not None else ""
                    loc = f" en {h['LocationName']}" if h.get("LocationName") and h["LocationName"] != "-" else ""
                    
                    status_text = ""
                    icon = "📝"
                    
                    if action == "CREAR":
                        icon = "🆕"
                        status_text = f"**Dado de alta** por *{user}* el {ts}{qty} - {note}"
                    elif action == "MODIFICAR":
                        icon = "✏️"
                        status_text = f"**Modificación** por *{user}* el {ts} - Motivo: {note}"
                    elif action == "ELIMINAR":
                        icon = "🗑️"
                        status_text = f"**Eliminación (archivado)** por *{user}* el {ts} - {note}"
                    elif action == "RESTAURAR":
                        icon = "🔄"
                        status_text = f"**Restauración** por *{user}* el {ts} - {note}"
                    elif action == "VENTA":
                        icon = "💰"
                        status_text = f"**Venta** registrada por *{user}* el {ts}{qty}{loc} - {note}"
                    elif action == "RESURTIDO":
                        icon = "📦"
                        status_text = f"**Resurtido** registrado por *{user}* el {ts}{qty} - {note}"
                    elif action == "REGALO":
                        icon = "🎁"
                        status_text = f"**Regalo** registrado por *{user}* el {ts}{qty} - Motivo: {note}"
                    elif action == "PERDIDA":
                        icon = "⚠️"
                        status_text = f"**Pérdida/Robo** registrado por *{user}* el {ts}{qty} - {note}"
                    elif action == "CORREGIR":
                        icon = "🛠️"
                        status_text = f"**Corrección** por *{user}* el {ts} - {note}"
                    else:
                        status_text = f"**{action}** por *{user}* el {ts} - {note}"
                        
                    if h["Superseded"] == 1:
                        status_text = f"~~{status_text}~~ *(Corregida/Superada)*"
                        icon = "❌"
                        
                    st.markdown(f"{icon} {status_text}")
                st.write("---")

        if not history_list:
            st.info("No hay transacciones registradas en el historial.")
        else:
            df_hist = pd.DataFrame(history_list)

            # Format the dataframe columns for better readability
            # Rename columns to show in UI
            rename_cols = {
                "Id": "ID",
                "Timestamp": "Fecha/Hora",
                "User": "Usuario",
                "ActionType": "Acción",
                "TargetType": "Tipo",
                "TargetId": "Código Objetivo",
                "Quantity": "Cantidad",
                "LocationName": "Lugar de Venta",
                "Note": "Nota/Motivo",
                "Superseded": "Corregida",
            }

            # Ensure correct columns exist in history dataframe
            df_display_hist = df_hist.copy()
            if "LocationId" in df_display_hist.columns:
                df_display_hist = df_display_hist.drop(columns=["LocationId"])

            # Fill NaN values for cleaner look
            df_display_hist["Quantity"] = df_display_hist["Quantity"].apply(
                lambda x: str(int(x)) if pd.notna(x) else "-"
            )
            df_display_hist["LocationName"] = df_display_hist["LocationName"].fillna("-")
            df_display_hist["Note"] = df_display_hist["Note"].fillna("-")

            # Display status "Sí" / "No" for Superseded
            if "Superseded" in df_display_hist.columns:
                df_display_hist["Superseded"] = df_display_hist["Superseded"].apply(
                    lambda x: "Sí" if x == 1 else "No"
                )

            # Reorder and filter columns
            col_order = [
                "Id",
                "Timestamp",
                "User",
                "ActionType",
                "TargetType",
                "TargetId",
                "Quantity",
                "LocationName",
                "Note",
                "Superseded",
            ]
            df_display_hist = df_display_hist[
                [c for c in col_order if c in df_display_hist.columns]
            ]
            df_display_hist = df_display_hist.rename(columns=rename_cols)  # pyright: ignore
            df_display_hist["Acción"] = df_display_hist["Acción"].replace({"CREAR": "ALTA"})

            st.dataframe(df_display_hist, hide_index=True)

            # Correction System
            st.write("---")
            st.subheader("Realizar corrección de transacción")

            @st.dialog("Corregir transacción")
            def correct_transaction_dialog(history_id_to_correct):
                # Fetch original item details
                orig_row = next(
                    (h for h in history_list if h["Id"] == history_id_to_correct), None
                )
                if not orig_row:
                    st.error("No se encontró la transacción.")
                    return

                st.write(
                    f"Corrigiendo transacción **ID {history_id_to_correct}** ({orig_row['ActionType']} - {orig_row['TargetId']})"
                )

                with st.form("correction_submit_form"):
                    new_date = st.text_input(
                        "Nueva fecha (YYYY-MM-DD):", value=orig_row["Timestamp"][:10]
                    )

                    # Location (Ventas only)
                    locs_list = service.get_locations()
                    loc_opts = {f"{loc['Id']} - {loc['Name']}": loc["Id"] for loc in locs_list}
                    loc_opts_keys = ["(Sin cambio)", *list(loc_opts.keys())]

                    selected_loc_lbl = st.selectbox(
                        "Nuevo lugar (solo para ventas):",
                        loc_opts_keys,
                        disabled=(orig_row["ActionType"] != "VENTA"),
                    )
                    new_loc_id = (
                        loc_opts.get(selected_loc_lbl)
                        if selected_loc_lbl != "(Sin cambio)"
                        else None
                    )

                    # Quantity spin
                    curr_qty = orig_row.get("Quantity")
                    new_qty = st.number_input(
                        "Nueva cantidad:",
                        min_value=1,
                        value=int(curr_qty) if curr_qty is not None else 1,
                        step=1,
                    )

                    reason = st.text_input("Motivo de la corrección (obligatorio):").strip()

                    submit_corr = st.form_submit_button("Confirmar corrección", icon=":material/check:", width="stretch")
                    if submit_corr:
                        if not reason:
                            st.error("El motivo de la corrección es obligatorio.")
                            return
                        if not new_date:
                            st.error("La fecha de corrección es obligatoria.")
                            return

                        try:
                            datetime.strptime(new_date, "%Y-%m-%d")
                        except ValueError:
                            st.error(
                                "La fecha ingresada es inválida. Use el formato YYYY-MM-DD."
                            )
                            return

                        with db_lock:
                            success = service.correct_transaction(
                                history_id=history_id_to_correct,
                                new_date=new_date,
                                new_location=new_loc_id,
                                new_quantity=int(new_qty),
                                reason=reason,
                            )
                        if success:
                            st.success(
                                "Transacción corregida exitosamente. Auditoría registrada."
                            )
                            st.rerun()
                        else:
                            st.error(
                                "Error al aplicar la corrección. Verifique la disponibilidad de stock o la validez del movimiento."
                            )

            # Select transaction ID to correct
            # Only allow correcting target type 'PULSERA'
            correctable_history = [
                h
                for h in history_list
                if h["TargetType"] == "PULSERA" and h["Superseded"] == 0
            ]
            if not correctable_history:
                st.info("No hay transacciones disponibles para corregir.")
            else:
                col_sel_id, col_btn_action = st.columns([3, 1])
                with col_sel_id:
                    history_choices = {
                        f"ID {h['Id']} - {h['Timestamp']} | {h['ActionType']} | {h['TargetId']} | Cant: {h['Quantity']}": h[
                            "Id"
                        ]
                        for h in correctable_history
                    }
                    selected_choice = st.selectbox(
                        "Seleccione la transacción a corregir:",
                        list(history_choices.keys()),
                        index = None,
                        placeholder="Seleccione o busque una transacción...",
                    )
                    chosen_history_id = history_choices[selected_choice] if selected_choice else None
                with col_btn_action:
                    st.write("")  # padding
                    st.write("")  # padding
                    if st.button(
                        "Corregir seleccionada", icon=":material/edit_note:", width="stretch", type="primary"
                    ):
                        correct_transaction_dialog(chosen_history_id)

# ----------------------------------------------------
# TAB 5: REPORTES EXCEL
# ----------------------------------------------------
if tab_rep.open:
    with tab_rep:
        st.subheader("Generación de reportes consolidados en Excel")
        st.write(
            "Genera y descarga reportes de inventario consolidados directamente en formato Excel."
        )

        export = ExportService(db.connection)

        # Contenedor ampliado con logo de Excel
        st.markdown(
            """
            <div style="
                border: 2px solid #e8c9b0;
                padding: 2.2rem 1.5rem;
                border-radius: 12px;
                background: white;
                text-align: center;
                margin-bottom: 0.0rem;
                box-shadow: 0 2px 8px rgba(0,0,0,0.04);
            ">
                <!-- Logo oficial Microsoft Excel (SVG) -->
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="70px" height="70px" style="margin-bottom: 0.8rem;">
                    <path fill="#107c41" d="M14.5,4h19c1.38,0,2.5,1.12,2.5,2.5v35c0,1.38-1.12,2.5-2.5,2.5h-19C13.12,44,12,42.88,12,41.5v-35C12,5.12,13.12,4,14.5,4z"/>
                    <path fill="#185c37" d="M33.5,4H24v40h9.5c1.38,0,2.5-1.12,2.5-2.5v-35C36,5.12,34.88,4,33.5,4z"/>
                    <path fill="#0e3a20" d="M36,13H24v11h12V13z"/>
                    <path fill="#107c41" d="M36,24H24v11h12V24z"/>
                    <path fill="#0c592b" d="M24,4h-9.5C13.12,4,12,5.12,12,6.5V13h12V4z"/>
                    <path fill="#107c41" d="M24,35H12v6.5C12,42.88,13.12,44,14.5,44H24V35z"/>
                    <path fill="#21a366" d="M7,13h18c1.1,0,2,0.9,2,2v18c0,1.1-0.9,2-2,2H7c-1.1,0-2-0.9-2-2V15C5,13.9,5.9,13,7,13z"/>
                    <path fill="#ffffff" d="M19.3,30.5l-2.9-4.9l-2.9,4.9H10.8l4.3-6.5l-4.1-6.5h2.8l2.7,4.8l2.7-4.8h2.7l-4.1,6.5l4.3,6.5H19.3z"/>
                </svg>
                <h3 style="margin: 0 0 0.5rem 0; color: #2c2c2c;">Reporte de Inventario Completo</h3>
                <p style="font-size: 0.95rem; color: #666; max-width: 600px; margin: 0 auto; line-height: 1.4;">
                    Genera un archivo Excel detallado con el inventario consolidado por material, histórico de resurtidos, regalos, pérdidas y ventas.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Generación del archivo y botón de descarga
        buffer_full = io.BytesIO()
        with db_lock:
            export.export_full_report(buffer_full)

        # Inyectar CSS para agrandar el botón de descarga
        st.markdown(
            """
            <style>
                /* 1. Altura y relleno del botón */
                div[data-testid="stDownloadButton"] button {
                    min-height: 100px !important;
                    padding: 1.2rem 2rem !important;
                    border-radius: 10px !important;
                }

                /* 2. Tamaño y grosor del texto */
                div[data-testid="stDownloadButton"] button p {
                    font-size: 1.2rem !important;
                    font-weight: 600 !important;
                }

                /* 3. Tamaño del icono de descarga */
                div[data-testid="stDownloadButton"] button span {
                    font-size: 1.5rem !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.download_button(
            label="Descargar reporte completo (.xlsx)",
            icon=":material/download:",
            data=buffer_full.getvalue(),
            file_name=f"Inventario_Ilumina_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
            type="primary",
        )

# ----------------------------------------------------
# TAB 6: INSTRUCTIVO
# ----------------------------------------------------
if tab_inst.open:
    with tab_inst:
        st.subheader(
            "Manual Operativo del Sistema de Inventario - Ilumina Mi Vida"
        )
        st.markdown(
            """
### 1. Acceso y Seguridad de Sesión
* **Credenciales:** Ingresa tu nombre de usuario y la contraseña maestra del sistema.
* **Registro de Auditoría:** Cada inicio y cierre de sesión queda registrado automáticamente en la bitácora de seguridad con fecha, hora y usuario.
* **Cierre de Sesión:** Utiliza el botón **Cerrar sesión** ubicado en la esquina superior derecha antes de abandonar la terminal o cambiar de turno.

---

### 2. Pestaña: Inventario
Permite visualizar, filtrar, agregar, editar y eliminar piezas de inventario.

* **Consulta y Filtros:** Puedes filtrar simultáneamente por **Código de pulsera**, **Material** (mediante menú desplegable) y **Descripción** (palabras clave del modelo). Haz clic sobre cualquier celda de la tabla para abrir el panel lateral derecho con la fotografía en alta resolución, precio unitario, stock disponible, total de piezas vendidas, ganancias acumuladas y fecha de alta.
* **Registro de Nueva Pulsera:**
  1. Haz clic en el botón azul **Registrar nueva pulsera**.
  2. Completa los campos: Código único (alfanumérico en mayúsculas), Material, Descripción, Precio ($), Stock inicial, Fecha de alta (`YYYY-MM-DD`) e Imagen opcional (.jpg/.png).
  3. Presiona **Guardar pulsera**. El sistema genera miniaturas y optimiza la imagen a 720px automáticamente.
* **Edición de Pulseras:** Selecciona la pulsera en la tabla, presiona **Editar pulsera**, modifica los valores deseados, ingresa obligatoriamente el **Motivo de la edición** y guarda los cambios.
* **Eliminación (Baja Lógica):** Presiona **Eliminar pulsera** y confirma. La pulsera se oculta del inventario activo pero conserva todo su historial financiero y operativo.

---

### 3. Pestaña: Movimientos
Módulo para asentar cualquier entrada o salida de mercancía en tiempo real.

* **Flujo de Registro:**
  1. Selecciona el tipo de movimiento: **🛒 Venta**, **📦 Resurtido**, **🎁 Regalo** o **⚠️ Pérdida**.
  2. **Pulsera:** Busca o escribe el código en el campo correspondiente (inicia vacío para evitar errores de captura).
  3. **Cantidad y Fecha:** Define las unidades y la fecha de la operación (`YYYY-MM-DD`).
  4. **Datos Específicos:**
     - **Venta:** Selecciona obligatoriamente el **Lugar de venta** oficial (4 letras) y añade notas opcionales.
     - **Resurtido:** Añade notas opcionales de lote o producción.
     - **Regalo:** Ingresa obligatoriamente el nombre de la persona, evento o institución en **Persona o motivo**.
     - **Pérdida:** Selecciona si corresponde a *"Robo"* o *"Pérdida"*.
  5. Presiona **Confirmar movimiento**. El sistema valida el stock físico disponible y muestra un aviso verde de confirmación por 2 segundos.
* **Bloqueo Automático:** El sistema rechaza cualquier salida que supere el stock físico disponible en bodega.

---

### 4. Pestaña: Materiales y Lugares
Administra los catálogos auxiliares requeridos por el sistema.

* **Materiales:** Permite dar de alta nuevas clasificaciones (ej. *Neopreno*, *Chaquira*), editar sus nombres, archivarlos o restaurarlos sin afectar pulseras existentes.
* **Lugares de Venta:** Registra puntos de venta asignando obligatoriamente un código de **exactamente 4 letras en mayúsculas** (ej. `AIMV`, `PLZD`, `LSBN`) y el nombre completo de la sucursal o bazar. Permite editar, archivar y restaurar ubicaciones.

---

### 5. Pestaña: Historial y Auditoría
Garantiza la trazabilidad total e inmutabilidad de la información contable.

* **Escudo Criptográfico:** Valida la cadena de hashes SHA-256 en cada fila. Verde indica integridad perfecta; rojo alerta sobre alteraciones externas directas a la base de datos.
* **Línea de Tiempo por Pulsera:** Ingresa cualquier código para ver la historia completa del modelo (creación, ventas, resurtidos, regalos y correcciones).
* **Corrección de Transacciones:** Si se comete un error de captura:
  1. Selecciona el ID de la transacción errónea en la sección inferior y haz clic en **Corregir seleccionada**.
  2. Ingresa los nuevos datos (fecha, lugar, cantidad) y el **Motivo de la corrección** obligatorio.
  3. Presiona **Confirmar corrección**. El sistema marca la transacción anterior como superada (`Superseded`), crea el nuevo registro corregido y recalcula automáticamente stock, ventas totales y ganancias.

---

### 6. Pestaña: Reportes Excel
Genera el concentrado contable y operativo listo para auditoría y dirección.

* Haz clic en **Descargar reporte completo (.xlsx)**.
* **Estructura del archivo descargado:**
  - **Hojas por material:** Una pestaña independiente para cada categoría de producto.
  - **Paneles congelados:** Las filas 1 a 4 se mantienen fijas en pantalla al desplazarse.
  - **Columnas Maestras:** `CÓDIGO`, `DESCRIPCIÓN`, `PRECIO`, `FECHA DE ALTA`.
  - **Columna GANANCIAS (Verde):** Ingreso monetario total acumulado por ventas.
  - **Columna PÉRDIDAS (Rojo):** Monto monetario acumulado por mermas y robos (`Cantidad × Precio`).
  - **STOCK ACTUAL (Rojo claro) y TOTAL DE VENTAS (Verde claro):** Balance físico de unidades.
  - **Columnas Cronológicas:** Cuadrícula dinámica desglosada por fecha y lugar para Resurtidos (amarillo), Regalos (morado), Pérdidas (rojo) y Ventas por sucursal (azul).

---

### 7. Buenas Prácticas y Prevención de Errores
* **Formato de Fechas:** Usa estrictamente la estructura estándar `YYYY-MM-DD` (ej. `2026-08-19`).
* **Códigos de Pulsera:** Evita espacios en blanco antes o después del texto y usa mayúsculas con guiones medios (ej. `PHROO-97`).
* **Tipificación de Salidas:** No registres mermas o regalos como ventas; utiliza las opciones correspondientes para que los balances financieros y las columnas de colores en Excel reflejen la realidad operativa.
"""
        )