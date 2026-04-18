from datetime import datetime, timezone
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
import json
import psycopg
from .db import get_conn
from .models import DeviceCreate, AssignmentCreate, AssignmentReturn
import paho.mqtt.client as mqtt

app = FastAPI(title="Inventar Starter", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))


def to_naive_utc(value: datetime) -> datetime:
    """Normalisiert aware/naive Datetimes auf naive UTC fuer konsistente Vergleiche."""
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value

def mqtt_client() -> mqtt.Client:
    c = mqtt.Client()
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    return c

@app.get("/health")
async def health():
    db_state = "ok"
    mqtt_state = "ok"
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
    except Exception as ex:
        db_state = f"error:{type(ex).__name__}"

    try:
        c = mqtt_client()
        c.disconnect()
    except Exception as ex:
        mqtt_state = f"degraded:{type(ex).__name__}"

    return {"status": "ok" if db_state == "ok" else "degraded", "db": db_state, "mqtt": mqtt_state}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Inventar Starter"})

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select d.device_id,
                   dt.name as device_type,
                   l.name as location,
                   d.status,
                   exists (
                       select 1
                       from assignment a
                       where a.device_id = d.device_id
                         and a.returned_at is null
                   ) as is_borrowed
            from device d
            join device_type dt on dt.device_type_id = d.device_type_id
            join location l on l.location_id = d.location_id
            order by d.device_id
            """
        )
        devices = list(cur.fetchall())

        cur.execute(
            """
            select device_type_id, name
            from device_type
            order by name
            """
        )
        device_types = list(cur.fetchall())

        cur.execute(
            """
            select location_id, name
            from location
            order by name
            """
        )
        locations = list(cur.fetchall())

    return templates.TemplateResponse(
        "inventory.html",
        {
            "request": request,
            "title": "Inventar Starter",
            "devices": devices,
            "device_types": device_types,
            "locations": locations,
        },
    )

@app.post("/mqtt/publish")
async def mqtt_publish(topic: str = Query(...), payload: str = Query(...)):
    c = mqtt_client()
    c.publish(topic, payload, qos=0, retain=False)
    c.disconnect()
    return {"ok": True, "topic": topic, "payload": payload}


@app.get("/devices")
async def get_devices():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select d.device_id,
                   d.serial_number,
                   d.inventory_number,
                   d.device_type_id,
                   dt.name as device_type,
                   d.location_id,
                   l.name as location,
                   d.status,
                   d.is_loanable,
                   d.created_at
            from device d
            join device_type dt on dt.device_type_id = d.device_type_id
            join location l on l.location_id = d.location_id
            order by d.device_id
            """
        )
        return list(cur.fetchall())


@app.post("/devices", status_code=201)
async def create_device(payload: DeviceCreate):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                insert into device (serial_number, inventory_number, device_type_id, location_id, status, is_loanable)
                values (%s, %s, %s, %s, %s, %s)
                returning device_id, serial_number, inventory_number, device_type_id, location_id, status, is_loanable, created_at
                """,
                (
                    payload.serial_number,
                    payload.inventory_number,
                    payload.device_type_id,
                    payload.location_id,
                    payload.status,
                    payload.is_loanable,
                ),
            )
            row = cur.fetchone()
            
            # Send MQTT event for device creation
            try:
                mqtt_event = {
                    "device_id": row["device_id"],
                    "serial_number": row["serial_number"],
                    "inventory_number": row["inventory_number"],
                    "device_type_id": row["device_type_id"],
                    "location_id": row["location_id"],
                    "status": row["status"],
                    "created_at": row["created_at"].isoformat(),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                c = mqtt_client()
                c.publish("inventory/devices/created", json.dumps(mqtt_event), qos=1, retain=False)
                c.disconnect()
            except Exception as ex:
                print(f"MQTT publish failed: {ex}")
            
            return row
        except psycopg.errors.UniqueViolation as ex:
            if "serial_number" in str(ex):
                raise HTTPException(status_code=409, detail="serial_number already exists")
            if "inventory_number" in str(ex):
                raise HTTPException(status_code=409, detail="inventory_number already exists")
            raise HTTPException(status_code=409, detail="duplicate key")
        except psycopg.errors.ForeignKeyViolation:
            raise HTTPException(status_code=422, detail="invalid device_type_id or location_id")
        except psycopg.errors.CheckViolation as ex:
            raise HTTPException(status_code=422, detail=f"invalid device payload: {ex}")


@app.get("/assignments/active")
async def get_active_assignments():
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select a.assignment_id,
                   a.device_id,
                   d.serial_number,
                   d.inventory_number,
                   a.person_id,
                   p.personnel_number,
                   p.first_name,
                   p.last_name,
                   a.assigned_at as issued_at,
                   a.due_at,
                   a.returned_at,
                   a.note
            from assignment a
            join device d on d.device_id = a.device_id
            join person p on p.person_id = a.person_id
            where a.returned_at is null
            order by a.assigned_at desc
            """
        )
        return list(cur.fetchall())


@app.post("/assignments", status_code=201)
async def create_assignment(payload: AssignmentCreate):
    issued_at = to_naive_utc(payload.issued_at) if payload.issued_at else datetime.now(timezone.utc).replace(tzinfo=None)
    due_at = to_naive_utc(payload.due_at) if payload.due_at else None

    if due_at is not None and due_at < issued_at:
        raise HTTPException(status_code=422, detail="due_at must not be before issued_at")

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("select 1 from device where device_id = %s", (payload.device_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="device not found")

        cur.execute("select 1 from person where person_id = %s", (payload.person_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="person not found")

        cur.execute(
            "select assignment_id from assignment where device_id = %s and returned_at is null",
            (payload.device_id,),
        )
        active = cur.fetchone()
        if active:
            raise HTTPException(status_code=409, detail="device already has an active assignment")

        try:
            cur.execute(
                """
                insert into assignment (device_id, person_id, assigned_at, due_at, note)
                values (%s, %s, %s, %s, %s)
                returning assignment_id, device_id, person_id, assigned_at as issued_at, due_at, returned_at, note
                """,
                (payload.device_id, payload.person_id, issued_at, due_at, payload.note),
            )
            row = cur.fetchone()

            cur.execute("update device set status = 'assigned' where device_id = %s", (payload.device_id,))
            return row
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail="device already has an active assignment")
        except psycopg.errors.CheckViolation as ex:
            raise HTTPException(status_code=422, detail=f"invalid assignment payload: {ex}")


@app.post("/assignments/{assignment_id}/return")
async def return_assignment(assignment_id: int, payload: AssignmentReturn):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            select assignment_id, device_id, assigned_at, returned_at
            from assignment
            where assignment_id = %s
            """,
            (assignment_id,),
        )
        row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="assignment not found")

        if row["returned_at"] is not None:
            raise HTTPException(status_code=409, detail="assignment already returned")

        returned_at = to_naive_utc(payload.returned_at) if payload.returned_at else datetime.now(timezone.utc).replace(tzinfo=None)
        issued_at = to_naive_utc(row["assigned_at"])

        # IR-03: returned_at darf nicht vor issued_at liegen
        if returned_at < issued_at:
            raise HTTPException(status_code=422, detail="returned_at must not be before issued_at")

        cur.execute(
            """
            update assignment
            set returned_at = %s
            where assignment_id = %s
            returning assignment_id, device_id, person_id, assigned_at as issued_at, due_at, returned_at, note
            """,
            (returned_at, assignment_id),
        )
        updated = cur.fetchone()

        cur.execute(
            """
            update device d
            set status = case
                when exists (
                    select 1 from assignment a
                    where a.device_id = d.device_id and a.returned_at is null
                ) then 'assigned'
                else 'available'
            end
            where d.device_id = %s
            """,
            (row["device_id"],),
        )

        return updated
