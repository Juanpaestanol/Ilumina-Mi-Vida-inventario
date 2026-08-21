import io
import pandas as pd
from PIL import Image


class ExportService:

    def __init__(self, conn):
        self.conn = conn

    def _safe_max_len(self, values):
        if isinstance(values, pd.DataFrame):
            if values.shape[1] == 0:
                return 0
            s = values.iloc[:, 0].astype(str)
        else:
            s = values.astype(str)
        if s.empty:
            return 0
        max_len = s.str.len().max()
        if pd.isna(max_len):
            return 0
        return max_len

    def export_full_report(self, filename: str | io.BytesIO):
        df_items = pd.read_sql_query(
            """
            SELECT i.Id, i.Description, i.Price, i.Stock, i.TotalSold, i.Ganancias, i.CreatedDate,
                   i.MaterialId, m.Name as MaterialName
            FROM Items i
            JOIN Materials m ON i.MaterialId = m.Id
            WHERE i.Deleted = 0
        """,
            self.conn,
        )

        # Solo incluir registros vigentes
        df_log = pd.read_sql_query(
            """
            SELECT h.Timestamp as Date, h.ActionType as Type, h.TargetId as ItemId,
                   h.Quantity, h.LocationId, h.Note, l.Name as LocationName
            FROM History h
            LEFT JOIN Locations l ON h.LocationId = l.Id
            WHERE h.Superseded = 0
              AND h.ActionType IN ('CREAR','RESURTIDO','VENTA','REGALO','PERDIDA')
        """,
            self.conn,
        )

        df_log["BaseType"] = df_log["Type"].str.replace("_CORRECTED", "")

        # Cálculo acumulado de pérdidas monetarias por pulsera (Piezas perdidas * Precio)
        df_loss_qty = (
            df_log[df_log["BaseType"] == "PERDIDA"]
            .groupby("ItemId")["Quantity"]
            .sum()
            .to_dict()
        )
        df_items["Perdidas"] = (
            df_items["Id"].map(df_loss_qty).fillna(0) * df_items["Price"]
        )

        with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
            workbook = writer.book
            fmt_header = workbook.add_format({
                "bold": True,
                "bg_color": "#D9D9D9",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_desc = workbook.add_format({
                "text_wrap": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_stock = workbook.add_format({
                "bg_color": "#F4CCCC",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_total = workbook.add_format({
                "bg_color": "#C6EFCE",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_ganancias = workbook.add_format({
                "bg_color": "#2AB646",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_color": "white",
                "num_format": "$#,##0.00",
            })
            # NUEVO: Formato rojo para la columna de pérdidas monetarias
            fmt_perdidas = workbook.add_format({
                "bg_color": "#E06666",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_color": "white",
                "num_format": "$#,##0.00",
            })
            fmt_res = workbook.add_format({
                "bg_color": "#FFF2CC",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_vent = workbook.add_format({
                "bg_color": "#CFE2F3",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_reg = workbook.add_format({
                "bg_color": "#D9D2E9",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_loss = workbook.add_format({
                "bg_color": "#F4CCCC",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_money = workbook.add_format({
                "num_format": "$#,##0.00",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_date = workbook.add_format({
                "num_format": "yyyy-mm-dd",
                "border": 1,
                "bg_color": "#D9D9D9",
                "bold": True,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_lugar = workbook.add_format({
                "bold": True,
                "italic": True,
                "align": "center",
                "valign": "vcenter",
                "border": 1,
                "bg_color": "#E8E8E8",
            })
            fmt_top_res = workbook.add_format({
                "bold": True,
                "bg_color": "#FFD966",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_top_vent = workbook.add_format({
                "bold": True,
                "bg_color": "#9FC5E8",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            })
            fmt_top_reg = workbook.add_format({
                "bold": True,
                "bg_color": "#8E7CC3",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_color": "white",
            })
            fmt_top_loss = workbook.add_format({
                "bold": True,
                "bg_color": "#E06666",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "font_color": "white",
            })

            for mat in df_items["MaterialName"].unique():
                df_hoja = df_items[df_items["MaterialName"] == mat].copy()

                # Se agrega Perdidas al DataFrame base
                base_cols = [
                    "Id",
                    "Description",
                    "Price",
                    "CreatedDate",
                    "Ganancias",
                    "Perdidas",
                    "Stock",
                    "TotalSold",
                ]
                df_base = df_hoja[base_cols].copy()
                df_base.columns = [
                    "CÓDIGO",
                    "DESCRIPCIÓN",
                    "PRECIO",
                    "FECHA DE ALTA",
                    "GANANCIAS",
                    "PÉRDIDAS",
                    "STOCK ACTUAL",
                    "TOTAL DE VENTAS",
                ]

                codes = df_hoja["Id"].tolist()
                logs_mat = df_log[df_log["ItemId"].isin(codes)].copy()
                if len(logs_mat) > 0:
                    # format='mixed' procesa fechas con y sin hora; .dt.normalize() trunca la hora a medianoche (00:00:00)
                    logs_mat["Date"] = pd.to_datetime(
                        logs_mat["Date"], format="mixed"
                    ).dt.normalize()
                    logs_mat = logs_mat.sort_values("Date")
                    logs_mat["GroupType"] = logs_mat["BaseType"]
                else:
                    logs_mat = pd.DataFrame(columns=logs_mat.columns)

                # Resurtidos
                logs_r = (
                    logs_mat[logs_mat["GroupType"].isin(["CREAR", "RESURTIDO"])]
                    if len(logs_mat) > 0
                    else pd.DataFrame()
                )
                if len(logs_r) > 0:
                    logs_r = logs_r.copy()
                    logs_r["LocationId"] = logs_r["LocationId"].fillna("-")
                    pivot_r = logs_r.pivot_table(
                        index="ItemId",
                        columns=["LocationId", "Date"],
                        values="Quantity",
                        aggfunc="sum",
                        sort=False,
                    )
                    pivot_r.columns = [
                        (
                            f"R|{loc if loc is not None else '-'}|{d.strftime('%Y-%m-%d')}"
                        )
                        for loc, d in pivot_r.columns
                    ]
                    df_base = df_base.merge(
                        pivot_r, left_on="CÓDIGO", right_index=True, how="left"
                    )
                    n_r = len(pivot_r.columns)
                else:
                    n_r = 0

                # Regalos
                logs_g = (
                    logs_mat[logs_mat["GroupType"] == "REGALO"]
                    if len(logs_mat) > 0
                    else pd.DataFrame()
                )
                if len(logs_g) > 0:
                    pivot_g = logs_g.pivot_table(
                        index="ItemId",
                        columns=["Note", "Date"],
                        values="Quantity",
                        aggfunc="sum",
                        sort=False,
                    )
                    pivot_g.columns = [
                        f"G|{note if note else ''}|{d.strftime('%Y-%m-%d')}"
                        for note, d in pivot_g.columns
                    ]
                    df_base = df_base.merge(
                        pivot_g, left_on="CÓDIGO", right_index=True, how="left"
                    )
                    n_g = len(pivot_g.columns)
                else:
                    n_g = 0

                # Pérdidas
                logs_p = (
                    logs_mat[logs_mat["GroupType"] == "PERDIDA"]
                    if len(logs_mat) > 0
                    else pd.DataFrame()
                )
                if len(logs_p) > 0:
                    pivot_p = logs_p.pivot_table(
                        index="ItemId",
                        columns=["Note", "Date"],
                        values="Quantity",
                        aggfunc="sum",
                        sort=False,
                    )
                    pivot_p.columns = [
                        f"P|{note if note else ''}|{d.strftime('%Y-%m-%d')}"
                        for note, d in pivot_p.columns
                    ]
                    df_base = df_base.merge(
                        pivot_p, left_on="CÓDIGO", right_index=True, how="left"
                    )
                    n_p = len(pivot_p.columns)
                else:
                    n_p = 0

                # Ventas
                logs_v = (
                    logs_mat[logs_mat["GroupType"] == "VENTA"]
                    if len(logs_mat) > 0
                    else pd.DataFrame()
                )
                if len(logs_v) > 0:
                    pivot_v = logs_v.pivot_table(
                        index="ItemId",
                        columns=["LocationId", "Date"],
                        values="Quantity",
                        aggfunc="sum",
                        sort=False,
                    )
                    pivot_v.columns = [
                        f"V|{loc if loc else '-'}|{d.strftime('%Y-%m-%d')}"
                        for loc, d in pivot_v.columns
                    ]
                    df_base = df_base.merge(
                        pivot_v, left_on="CÓDIGO", right_index=True, how="left"
                    )
                    n_v = len(pivot_v.columns)
                else:
                    n_v = 0

                df_base = df_base.fillna("-")
                sheet_name = str(mat)[:31]
                df_base.to_excel(
                    writer,
                    sheet_name=sheet_name,
                    index=False,
                    startrow=4,
                    header=False,
                )
                ws = writer.sheets[sheet_name]

                ws.freeze_panes(4,1)

                # Escribir cabeceras y dar formato a columnas
                for i, col in enumerate(df_base.columns):
                    if "|" in col:
                        parts = col.split("|")
                        tipo, lug, fec = parts[0], parts[1], parts[2]
                        ws.write(1, i, lug if lug != "-" else "", fmt_lugar)
                        ws.write(2, i, fec, fmt_date)
                        ws.write(3, i, "PIEZAS", fmt_header)
                        if tipo == "R":
                            est = fmt_res
                            group_count = n_r
                            group_title = "RESURTIDOS / ENTRADAS"
                        elif tipo == "G":
                            est = fmt_reg
                            group_count = n_g
                            group_title = "REGALOS"
                        elif tipo == "P":
                            est = fmt_loss
                            group_count = n_p
                            group_title = "PÉRDIDAS"
                        else:
                            est = fmt_vent
                            group_count = n_v
                            group_title = "VENTAS POR LUGAR"

                        values = df_base[col]
                        max_len_val = self._safe_max_len(values)
                        width_candidates = [
                            len(lug),
                            len(fec),
                            len("PIEZAS"),
                            max_len_val,
                        ]
                        col_width = max(width_candidates) + 2
                        if group_count == 1:
                            col_width = max(col_width, len(group_title) + 2)
                        ws.set_column(i, i, col_width, est)
                    else:
                        if col == "PRECIO":
                            est = fmt_money
                        elif col == "GANANCIAS":
                            est = fmt_ganancias
                        elif col == "PÉRDIDAS":
                            est = fmt_perdidas
                        elif col == "STOCK ACTUAL":
                            est = fmt_stock
                        elif col == "TOTAL DE VENTAS":
                            est = fmt_total
                        elif col == "FECHA DE ALTA":
                            est = fmt_date
                        elif col == "DESCRIPCIÓN":
                            est = fmt_desc
                            ws.set_column(i, i, 47, est)
                            ws.write(3, i, col, fmt_header)
                            continue
                        else:
                            est = None
                        max_len_val = self._safe_max_len(df_base[col])
                        max_len = max(max_len_val, len(col)) + 2
                        ws.set_column(i, i, max_len, est)
                        ws.write(3, i, col, fmt_header)

                # Cabeceras superiores agrupadas (c_start = 8 por la nueva columna)
                c_start = 8
                if n_r > 0:
                    if n_r == 1:
                        ws.write(
                            0, c_start, "RESURTIDOS / ENTRADAS", fmt_top_res
                        )
                    else:
                        ws.merge_range(
                            0,
                            c_start,
                            0,
                            c_start + n_r - 1,
                            "RESURTIDOS / ENTRADAS",
                            fmt_top_res,
                        )
                    c_start += n_r
                if n_g > 0:
                    if n_g == 1:
                        ws.write(0, c_start, "REGALOS", fmt_top_reg)
                    else:
                        ws.merge_range(
                            0,
                            c_start,
                            0,
                            c_start + n_g - 1,
                            "REGALOS",
                            fmt_top_reg,
                        )
                    c_start += n_g
                if n_p > 0:
                    if n_p == 1:
                        ws.write(0, c_start, "PÉRDIDAS", fmt_top_loss)
                    else:
                        ws.merge_range(
                            0,
                            c_start,
                            0,
                            c_start + n_p - 1,
                            "PÉRDIDAS",
                            fmt_top_loss,
                        )
                    c_start += n_p
                if n_v > 0:
                    if n_v == 1:
                        ws.write(0, c_start, "VENTAS POR LUGAR", fmt_top_vent)
                    else:
                        ws.merge_range(
                            0,
                            c_start,
                            0,
                            c_start + n_v - 1,
                            "VENTAS POR LUGAR",
                            fmt_top_vent,
                        )

    def export_visual_catalogue(self, filename: str | io.BytesIO):
        df_items = pd.read_sql_query(
            """
            SELECT Id, Description, Price, MaterialId, ImageData
            FROM Items
            WHERE Deleted = 0
        """,
            self.conn,
        )
        df_materials = pd.read_sql_query(
            "SELECT Id AS MaterialId, Name FROM Materials", self.conn
        )
        df_items = df_items.merge(df_materials, on="MaterialId")

        with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
            money_fmt = writer.book.add_format({
                "num_format": "$#,##0.00",
                "border": 1,
                "valign": "vcenter",
                "align": "center",
            })
            desc_fmt = writer.book.add_format({
                "text_wrap": True,
                "border": 1,
                "valign": "vcenter",
                "align": "center",
            })
            base_fmt = writer.book.add_format(
                {"border": 1, "valign": "vcenter", "align": "center"}
            )
            header_fmt = writer.book.add_format({
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#D9D9D9",
            })

            for mat in df_items["Name"].unique():
                temp = df_items[df_items["Name"] == mat][
                    ["Id", "Description", "Price", "ImageData"]
                ]
                temp.columns = ["CÓDIGO", "DESCRIPCIÓN", "PRECIO", "ImageData"]
                sheet_name = str(mat)[:31]
                temp_no_img = temp.drop(columns=["ImageData"])
                temp_no_img.to_excel(writer, sheet_name=sheet_name, index=False)
                ws = writer.sheets[sheet_name]
                ws.set_column("A:A", 15, base_fmt)
                ws.set_column("B:B", 47, desc_fmt)
                ws.set_column("C:C", 15, money_fmt)
                ws.set_column("D:D", 30)
                for col_num, value in enumerate(temp_no_img.columns):
                    ws.write(0, col_num, value, header_fmt)
                ws.write("D1", "VISTA PREVIA", header_fmt)

                for i, (_cod, blob) in enumerate(
                    zip(temp["CÓDIGO"], temp["ImageData"], strict=False),
                    start=1,
                ):
                    ws.set_row(i, 125)
                    if blob:
                        try:
                            image_bytes = io.BytesIO(blob)
                            with Image.open(image_bytes) as img:
                                w, h = img.size
                            scale = min(180 / w, 120 / h)
                            image_bytes.seek(0)
                            ws.insert_image(
                                i,
                                3,
                                "",
                                {
                                    "image_data": image_bytes,
                                    "x_scale": scale,
                                    "y_scale": scale,
                                    "x_offset": 5,
                                    "y_offset": 2,
                                    "object_position": 1,
                                },
                            )
                        except Exception:
                            ws.write(i, 3, "Error imagen", base_fmt)
                    else:
                        ws.write(i, 3, "Sin imagen", base_fmt)

    def export_location_catalogue(self, filename: str | io.BytesIO):
        df_locs = pd.read_sql_query(
            "SELECT Id, Name FROM Locations ORDER BY Id", self.conn
        )
        df_locs.columns = ["ID CÓDIGO", "NOMBRE COMPLETO DEL LUGAR"]
        with pd.ExcelWriter(filename, engine="xlsxwriter") as writer:
            df_locs.to_excel(
                writer, index=False, sheet_name="Catálogo de lugares"
            )
            ws = writer.sheets["Catálogo de lugares"]
            ws.set_column("A:A", 15)
            ws.set_column("B:B", 50)