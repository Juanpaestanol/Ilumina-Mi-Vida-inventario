import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from src.utils.image_utils import process_image


class InventoryService:
    def __init__(self, conn: sqlite3.Connection, user: str):
        self.conn = conn
        self.user = user

    # ---- Helper: log to History ----
    def _log_history(
        self,
        action_type: str,
        target_type: str,
        target_id: str,
        quantity: int | None = None,
        location_id: str | None = None,
        note: str | None = None,
        old_values: dict | None = None,
        new_values: dict | None = None,
        original_id: int | None = None,
        ganancias_delta: float | None = None,
    ):
        cursor = self.conn.cursor()
        
        # Get the previous hash
        cursor.execute("SELECT LogHash FROM History ORDER BY Id DESC LIMIT 1")
        last_row = cursor.fetchone()
        prev_hash = last_row[0] if last_row else ""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        old_val_str = json.dumps(old_values) if old_values else None
        new_val_str = json.dumps(new_values) if new_values else None
        
        # Calculate cryptographic hash
        payload = f"{timestamp}|{self.user}|{action_type}|{target_type}|{target_id}|" \
                  f"{quantity or 0}|{location_id or ''}|{note or ''}|" \
                  f"{old_val_str or ''}|{new_val_str or ''}|" \
                  f"{original_id or 0}|{ganancias_delta or 0.0}|{prev_hash}"
        log_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        cursor.execute(
            """
            INSERT INTO History (
                Timestamp, User, ActionType, TargetType, TargetId,
                Quantity, LocationId, Note, OldValues, NewValues, OriginalId, Superseded, GananciasDelta, LogHash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
            (
                timestamp,
                self.user,
                action_type,
                target_type,
                target_id,
                quantity,
                location_id,
                note,
                old_val_str,
                new_val_str,
                original_id,
                ganancias_delta,
                log_hash,
            ),
        )
        self.conn.commit()

    def verify_log_integrity(self) -> dict[str, Any]:
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT Id, Timestamp, User, ActionType, TargetType, TargetId,
                   Quantity, LocationId, Note, OldValues, NewValues, OriginalId,
                   GananciasDelta, LogHash
            FROM History
            ORDER BY Id ASC
        """)
        rows = cursor.fetchall()
        
        tampered_ids = []
        prev_hash = ""
        
        for row in rows:
            r_id, timestamp, user, action_type, target_type, target_id, qty, loc_id, note, old_val, new_val, orig_id, gan_delta, log_hash = row
            
            # Recalculate hash
            payload = f"{timestamp}|{user}|{action_type}|{target_type}|{target_id}|" \
                      f"{qty or 0}|{loc_id or ''}|{note or ''}|" \
                      f"{old_val or ''}|{new_val or ''}|" \
                      f"{orig_id or 0}|{gan_delta or 0.0}|{prev_hash}"
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            
            if log_hash != expected_hash:
                tampered_ids.append(r_id)
            
            prev_hash = log_hash if log_hash else ""
            
        return {
            "status": len(tampered_ids) == 0,
            "tampered_ids": tampered_ids
        }

    # ---- Generic event log ----
    def log_event(
        self,
        action_type: str,
        note: str,
        target_type: str | None = None,
        target_id: str | None = None,
    ):
        self._log_history(
            action_type=action_type,
            target_type=target_type or "SYSTEM",
            target_id=target_id or "N/A",
            note=note,
        )

    # ---- Materials ----
    def get_materials(self, include_deleted: bool = False) -> list[dict]:
        cursor = self.conn.cursor()
        if include_deleted:
            cursor.execute("SELECT Id, Name, Deleted FROM Materials ORDER BY Name")
            rows = cursor.fetchall()
            return [{"Id": r[0], "Name": r[1], "Deleted": r[2]} for r in rows]
        else:
            cursor.execute("SELECT Id, Name FROM Materials WHERE Deleted = 0 ORDER BY Name")
            rows = cursor.fetchall()
            return [{"Id": r[0], "Name": r[1]} for r in rows]

    def add_material(self, name: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO Materials (Name) VALUES (?)", (name,))
            self.conn.commit()
            self._log_history(
                action_type="CREAR",
                target_type="MATERIAL",
                target_id=str(cursor.lastrowid),
                new_values={"Name": name},
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def edit_material(self, material_id: int, new_name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT Name FROM Materials WHERE Id = ?", (material_id,))
        row = cursor.fetchone()
        if not row:
            return False
        old_name = row[0]
        if old_name == new_name:
            return True
        try:
            cursor.execute(
                "UPDATE Materials SET Name = ? WHERE Id = ?", (new_name, material_id)
            )
            self.conn.commit()
            self._log_history(
                action_type="MODIFICAR",
                target_type="MATERIAL",
                target_id=str(material_id),
                old_values={"Name": old_name},
                new_values={"Name": new_name},
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_material(self, material_id: int) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE Materials SET Deleted = 1 WHERE Id = ?", (material_id,))
            self.conn.commit()
            self._log_history(
                action_type="ELIMINAR",
                target_type="MATERIAL",
                target_id=str(material_id),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def restore_material(self, material_id: int) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE Materials SET Deleted = 0 WHERE Id = ?", (material_id,))
            self.conn.commit()
            self._log_history(
                action_type="RESTAURAR",
                target_type="MATERIAL",
                target_id=str(material_id),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    # ---- Locations ----
    def get_locations(self, include_deleted: bool = False) -> list[dict]:
        cursor = self.conn.cursor()
        if include_deleted:
            cursor.execute("SELECT Id, Name, Deleted FROM Locations ORDER BY Id")
            rows = cursor.fetchall()
            return [{"Id": r[0], "Name": r[1], "Deleted": r[2]} for r in rows]
        else:
            cursor.execute("SELECT Id, Name FROM Locations WHERE Deleted = 0 ORDER BY Id")
            rows = cursor.fetchall()
            return [{"Id": r[0], "Name": r[1]} for r in rows]

    def add_location(self, loc_id: str, name: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO Locations (Id, Name) VALUES (?, ?)", (loc_id.upper(), name)
            )
            self.conn.commit()
            self._log_history(
                action_type="CREAR",
                target_type="LUGAR",
                target_id=loc_id.upper(),
                new_values={"Id": loc_id.upper(), "Name": name},
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def edit_location(self, loc_id: str, new_id: str, new_name: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT Id, Name FROM Locations WHERE Id = ?", (loc_id,))
        row = cursor.fetchone()
        if not row:
            return False
        old_id, old_name = row
        if old_id == new_id and old_name == new_name:
            return True
        try:
            cursor.execute(
                "UPDATE Locations SET Id = ?, Name = ? WHERE Id = ?",
                (new_id.upper(), new_name, loc_id),
            )
            self.conn.commit()
            self._log_history(
                action_type="MODIFICAR",
                target_type="LUGAR",
                target_id=new_id.upper(),
                old_values={"Id": old_id, "Name": old_name},
                new_values={"Id": new_id.upper(), "Name": new_name},
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_location(self, loc_id: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE Locations SET Deleted = 1 WHERE Id = ?", (loc_id,))
            self.conn.commit()
            self._log_history(
                action_type="ELIMINAR", target_type="LUGAR", target_id=loc_id
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def restore_location(self, loc_id: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE Locations SET Deleted = 0 WHERE Id = ?", (loc_id,))
            self.conn.commit()
            self._log_history(
                action_type="RESTAURAR", target_type="LUGAR", target_id=loc_id
            )
            return True
        except sqlite3.IntegrityError:
            return False

    # ---- Items ----
    def get_all_items(self, include_deleted: bool = False) -> list[dict]:
        cursor = self.conn.cursor()
        query = """
            SELECT i.Id, i.Description, i.Price, i.Stock, i.TotalSold, i.CreatedDate, i.ThumbnailData, i.Deleted,
                   m.Id as MaterialId, m.Name as MaterialName
            FROM Items i
            JOIN Materials m ON i.MaterialId = m.Id
        """
        if not include_deleted:
            query += " WHERE i.Deleted = 0"
        query += " ORDER BY i.Id"
        cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    def get_item(self, item_id: str) -> dict | None:
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT i.*, m.Name as MaterialName
            FROM Items i
            JOIN Materials m ON i.MaterialId = m.Id
            WHERE i.Id = ?
        """,
            (item_id,),
        )
        row = cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row, strict=False))
        return None

    def add_item(self, item: dict) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO Items (Id, MaterialId, Description, Price, Stock, TotalSold, CreatedDate, ImageData, ThumbnailData)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            """,
                (
                    item["Id"],
                    item["MaterialId"],
                    item["Description"],
                    item["Price"],
                    item["Stock"],
                    item["CreatedDate"],
                    item.get("ImageData"),
                    item.get("ThumbnailData"),
                ),
            )
            self.conn.commit()
            self._log_history(
                action_type="CREAR",
                target_type="PULSERA",
                target_id=item["Id"],
                quantity=item["Stock"],
                new_values={
                    "Id": item["Id"],
                    "MaterialId": item["MaterialId"],
                    "Description": item["Description"],
                    "Price": item["Price"],
                    "Stock": item["Stock"],
                    "CreatedDate": item["CreatedDate"],
                },
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_item(self, item_id: str, data: dict, note: str | None = None) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Items WHERE Id = ?", (item_id,))
        old_row = cursor.fetchone()
        if not old_row:
            return False
        old_cols = [desc[0] for desc in cursor.description]
        old_item = dict(zip(old_cols, old_row, strict=False))

        try:
            old_id = item_id
            new_id = data.get("Id", old_id)
            set_clause = []
            params = []
            changed = {}
            for key in [
                "MaterialId",
                "Description",
                "Price",
                "Stock",
                "CreatedDate",
                "ImageData",
                "ThumbnailData",
            ]:
                if key in data:
                    set_clause.append(f"{key} = ?")
                    params.append(data[key])
                    if str(old_item.get(key)) != str(data[key]):
                        changed[key] = data[key]
            if new_id != old_id:
                set_clause.append("Id = ?")
                params.append(new_id)
                changed["Id"] = new_id
            if not changed:
                return True
            params.append(old_id)
            query = f"UPDATE Items SET {', '.join(set_clause)} WHERE Id = ?"
            if params:
                cursor.execute(query, tuple(params))
            else:
                cursor.execute(query)
            self.conn.commit()

            old_vals: dict[str, Any] = {}
            new_vals: dict[str, Any] = {}
            for k, v in changed.items():
                if k in ("ImageData", "ThumbnailData"):
                    old_vals[k] = "<binary>"
                    new_vals[k] = "<binary>"
                else:
                    old_vals[k] = old_item.get(k)
                    new_vals[k] = v

            self._log_history(
                action_type="MODIFICAR",
                target_type="PULSERA",
                target_id=new_id,
                note=note,
                old_values=old_vals,
                new_values=new_vals,
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_item(self, item_id: str) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM Items WHERE Id = ?", (item_id,))
        row = cursor.fetchone()
        if not row:
            return False
        cols = [desc[0] for desc in cursor.description]
        item_data = dict(zip(cols, row, strict=False))

        try:
            cursor.execute("UPDATE Items SET Deleted = 1 WHERE Id = ?", (item_id,))
            self.conn.commit()
            self._log_history(
                action_type="ELIMINAR",
                target_type="PULSERA",
                target_id=item_id,
                old_values=item_data,
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def restore_item(self, item_id: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("UPDATE Items SET Deleted = 0 WHERE Id = ?", (item_id,))
            self.conn.commit()
            self._log_history(
                action_type="RESTAURAR", target_type="PULSERA", target_id=item_id
            )
            return True
        except sqlite3.IntegrityError:
            return False

    # ---- History ----
    def get_history(
        self,
        target_type: str | None = None,
        target_id: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        cursor = self.conn.cursor()
        query = """
            SELECT h.*, l.Name as LocationName
            FROM History h
            LEFT JOIN Locations l ON h.LocationId = l.Id
        """
        conditions = []
        params: list[Any] = []
        if target_type:
            conditions.append("h.TargetType = ?")
            params.append(target_type)
        if target_id:
            conditions.append("h.TargetId = ?")
            params.append(target_id)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY h.Timestamp DESC, h.Id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        if params:
            cursor.execute(query, tuple(params))
        else:
            cursor.execute(query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    # ---- Inventory movements ----
    def _inventory_movement(
        self,
        action_type: str,
        item_id: str,
        quantity: int,
        date: str,
        location_id: str | None = None,
        note: str | None = None,
    ) -> bool:
        cursor = self.conn.cursor()
        if action_type in ("VENTA", "REGALO", "PERDIDA"):
            cursor.execute(
                "SELECT Stock, Price FROM Items WHERE Id = ? AND Deleted = 0", (item_id,)
            )
            row = cursor.fetchone()
            if not row or row[0] < quantity:
                return False
            stock, price = row
            cursor.execute(
                "UPDATE Items SET Stock = Stock - ? WHERE Id = ?", (quantity, item_id)
            )
            if action_type == "VENTA":
                ganancia = price * quantity
                cursor.execute(
                    "UPDATE Items SET TotalSold = TotalSold + ?, Ganancias = Ganancias + ? WHERE Id = ?",
                    (quantity, ganancia, item_id),
                )
        elif action_type in ("ALTA", "RESURTIDO"):
            cursor.execute(
                "UPDATE Items SET Stock = Stock + ? WHERE Id = ?", (quantity, item_id)
            )
        else:
            return False

        self.conn.commit()

        ganancias_delta = None
        if action_type == "VENTA":
            ganancias_delta = price * quantity

        self._log_history(
            action_type=action_type,
            target_type="PULSERA",
            target_id=item_id,
            quantity=quantity,
            location_id=location_id,
            note=note,
            new_values={"Stock": f"±{quantity}"},
            ganancias_delta=ganancias_delta,
        )
        return True

    def register_sale(
        self,
        item_id: str,
        location_id: str,
        quantity: int,
        date: str,
        note: str | None = None,
    ) -> bool:
        return self._inventory_movement(
            "VENTA", item_id, quantity, date, location_id, note
        )

    def register_restock(
        self, item_id: str, quantity: int, date: str, note: str | None = None
    ) -> bool:
        return self._inventory_movement(
            "RESURTIDO", item_id, quantity, date, None, note
        )

    def register_gift(self, item_id: str, note: str, quantity: int, date: str) -> bool:
        return self._inventory_movement("REGALO", item_id, quantity, date, None, note)

    def register_loss(self, item_id: str, note: str, quantity: int, date: str) -> bool:
        return self._inventory_movement("PERDIDA", item_id, quantity, date, None, note)

    # ---- Correction system ----
    def correct_transaction(
        self,
        history_id: int,
        new_date: str | None = None,
        new_location: str | None = None,
        new_quantity: int | None = None,
        new_item_id: str | None = None,
        reason: str | None = None,
    ) -> bool:
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM History WHERE Id = ?", (history_id,))
        original = cursor.fetchone()
        if not original:
            return False
        cols = [desc[0] for desc in cursor.description]
        orig_data = dict(zip(cols, original, strict=False))

        if orig_data["TargetType"] not in ("PULSERA", "ITEM"):
            return False

        old_vals: dict[str, Any] = {}
        changes: dict[str, Any] = {}
        action = orig_data["ActionType"]
        target_id = orig_data["TargetId"]
        old_qty = orig_data["Quantity"]
        old_loc = orig_data.get("LocationId")
        old_date = orig_data["Timestamp"][:10]

        if new_date and new_date != old_date:
            old_vals["Date"] = old_date
            changes["Date"] = new_date

        if new_location is not None and action == "VENTA":
            if new_location != old_loc:
                old_vals["LocationId"] = old_loc
                changes["LocationId"] = new_location

        if new_quantity is not None and new_quantity != old_qty:
            old_vals["Quantity"] = old_qty
            changes["Quantity"] = new_quantity

        if new_item_id and new_item_id != target_id:
            old_vals["ItemId"] = target_id
            changes["ItemId"] = new_item_id

        if not changes:
            return True

        cursor.execute("SELECT Price FROM Items WHERE Id = ?", (target_id,))
        item_row = cursor.fetchone()
        target_price = item_row[0] if item_row else 0.0

        # ---- Stock adjustments ----
        net_gan_delta = 0.0
        if "Quantity" in changes or "ItemId" in changes:
            qty_diff = (new_quantity if new_quantity is not None else old_qty) - old_qty

            if action in ("VENTA", "REGALO", "PERDIDA"):
                if qty_diff > 0:
                    cursor.execute(
                        "UPDATE Items SET Stock = Stock - ? WHERE Id = ?",
                        (qty_diff, target_id),
                    )
                    if action == "VENTA":
                        gan_diff = qty_diff * target_price
                        net_gan_delta += gan_diff
                        cursor.execute(
                            "UPDATE Items SET TotalSold = TotalSold + ?, Ganancias = Ganancias + ? WHERE Id = ?",
                            (qty_diff, gan_diff, target_id),
                        )
                else:
                    cursor.execute(
                        "UPDATE Items SET Stock = Stock + ? WHERE Id = ?",
                        (abs(qty_diff), target_id),
                    )
                    if action == "VENTA":
                        gan_diff = abs(qty_diff) * target_price
                        net_gan_delta -= gan_diff
                        cursor.execute(
                            "UPDATE Items SET TotalSold = TotalSold - ?, Ganancias = Ganancias - ? WHERE Id = ?",
                            (abs(qty_diff), gan_diff, target_id),
                        )
            elif action in ("ALTA", "CREAR", "RESURTIDO"):
                if qty_diff > 0:
                    cursor.execute(
                        "UPDATE Items SET Stock = Stock + ? WHERE Id = ?",
                        (qty_diff, target_id),
                    )
                else:
                    cursor.execute(
                        "UPDATE Items SET Stock = Stock - ? WHERE Id = ?",
                        (abs(qty_diff), target_id),
                    )
            self.conn.commit()

        if "ItemId" in changes:
            old_item = target_id
            new_item = new_item_id
            orig_effect_qty = old_qty if old_qty else 0

            cursor.execute("SELECT Price FROM Items WHERE Id = ?", (old_item,))
            old_item_row = cursor.fetchone()
            old_price = old_item_row[0] if old_item_row else 0.0

            cursor.execute("SELECT Price FROM Items WHERE Id = ?", (new_item,))
            new_item_row = cursor.fetchone()
            new_price = new_item_row[0] if new_item_row else 0.0

            if action in ("VENTA", "REGALO", "PERDIDA"):
                cursor.execute(
                    "UPDATE Items SET Stock = Stock + ? WHERE Id = ?",
                    (orig_effect_qty, old_item),
                )
                if action == "VENTA":
                    old_gan_refund = orig_effect_qty * old_price
                    net_gan_delta -= old_gan_refund
                    cursor.execute(
                        "UPDATE Items SET TotalSold = TotalSold - ?, Ganancias = Ganancias - ? WHERE Id = ?",
                        (orig_effect_qty, old_gan_refund, old_item),
                    )
            elif action in ("ALTA", "RESURTIDO"):
                cursor.execute(
                    "UPDATE Items SET Stock = Stock - ? WHERE Id = ?",
                    (orig_effect_qty, old_item),
                )

            new_qty_corrected = new_quantity if new_quantity is not None else old_qty
            if action in ("VENTA", "REGALO", "PERDIDA"):
                cursor.execute(
                    "UPDATE Items SET Stock = Stock - ? WHERE Id = ?",
                    (new_qty_corrected, new_item),
                )
                if action == "VENTA":
                    new_gan_charge = new_qty_corrected * new_price
                    net_gan_delta += new_gan_charge
                    cursor.execute(
                        "UPDATE Items SET TotalSold = TotalSold + ?, Ganancias = Ganancias + ? WHERE Id = ?",
                        (new_qty_corrected, new_gan_charge, new_item),
                    )
            elif action in ("ALTA", "RESURTIDO"):
                cursor.execute(
                    "UPDATE Items SET Stock = Stock + ? WHERE Id = ?",
                    (new_qty_corrected, new_item),
                )
            self.conn.commit()

        # ---- Mark original as superseded ----
        cursor.execute("UPDATE History SET Superseded = 1 WHERE Id = ?", (history_id,))
        self.conn.commit()

        # ---- Log correction ----
        note_text = f"Corrección de transacción ID {history_id}"
        if reason:
            note_text += f" - {reason}"
        for key, val in changes.items():
            note_text += f" | {key}: {old_vals.get(key)} → {val}"

        self._log_history(
            action_type="CORREGIR",
            target_type="TRANSACCION",
            target_id=str(history_id),
            quantity=orig_data["Quantity"],
            location_id=changes.get("LocationId", orig_data.get("LocationId")),
            note=note_text,
            old_values=old_vals,
            new_values=changes,
            original_id=history_id,
            ganancias_delta=net_gan_delta if action == "VENTA" else None,
        )

        corrected_action = action
        corrected_qty = new_quantity if new_quantity is not None else old_qty
        corrected_target = new_item_id if new_item_id is not None else target_id

        corrected_ganancias = None
        if action == "VENTA":
            price_to_use = new_price if "ItemId" in changes else target_price
            corrected_ganancias = corrected_qty * price_to_use

        self._log_history(
            action_type=corrected_action,
            target_type="PULSERA",
            target_id=corrected_target,
            quantity=corrected_qty,
            location_id=changes.get("LocationId", orig_data.get("LocationId")),
            note=f"Movimiento corregido (original ID {history_id})",
            original_id=history_id,
            ganancias_delta=corrected_ganancias,
        )

        return True

    # ---- Thumbnail generation ----
    def generate_missing_thumbnails(self, progress_callback=None) -> int:
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT Id, ImageData FROM Items WHERE ImageData IS NOT NULL AND ThumbnailData IS NULL AND Deleted = 0"
        )
        rows = cursor.fetchall()
        count = len(rows)
        if count == 0:
            return 0

        processed = 0
        for item_id, image_data in rows:
            try:
                thumb = process_image(image_data, 140)
                cursor.execute(
                    "UPDATE Items SET ThumbnailData = ? WHERE Id = ?", (thumb, item_id)
                )
                self.conn.commit()
                processed += 1
                if progress_callback:
                    progress_callback(processed, count)
            except Exception as e:
                print(f"Error generating thumbnail for {item_id}: {e}")
        return processed
