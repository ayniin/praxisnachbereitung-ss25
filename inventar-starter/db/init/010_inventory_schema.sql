-- 010_inventory_schema.sql
-- Inventar-Domaene fuer Tag 3
--
-- Hinweis:
--   Keine manuelle Tabellenerstellung in der DB; alles ueber Init-SQL.

-- 1) Stammdaten
create table if not exists department (
	department_id serial primary key,
	name          text not null unique
);

create table if not exists person (
	person_id           serial primary key,
	personnel_number    text not null unique,
	first_name          text not null,
	last_name           text not null,
	email               text not null unique,
	department_id       int  not null references department(department_id) on delete restrict,
	is_active           boolean not null default true,
	created_at          timestamp not null default now()
);

create table if not exists device_type (
	device_type_id      serial primary key,
	name                text not null unique
);

create table if not exists location (
	location_id         serial primary key,
	name                text not null unique
);

-- 2) Device
create table if not exists device (
	device_id           serial primary key,
	serial_number       text not null unique,
	inventory_number    text not null unique,
	device_type_id      int  not null references device_type(device_type_id) on delete restrict,
	location_id         int  not null references location(location_id) on delete restrict,
	status              text not null default 'available' check (status in ('available', 'assigned', 'repair', 'retired')),
	is_loanable         boolean not null default true,
	created_at          timestamp not null default now()
);

-- 3) Assignment (Ausleih-Historie)
create table if not exists assignment (
	assignment_id       serial primary key,
	device_id           int not null references device(device_id) on delete restrict,
	person_id           int not null references person(person_id) on delete restrict,
	assigned_at         timestamp not null default now(),
	due_at              timestamp,
	returned_at         timestamp,
	note                text,
	check (due_at is null or due_at >= assigned_at),
	check (returned_at is null or returned_at >= assigned_at)
);

-- Optionaler Schutz: nur eine aktive Zuweisung pro Device
create unique index if not exists uq_assignment_active_device
	on assignment(device_id)
	where returned_at is null;


-- ==========================================
-- Seed-Daten
-- ==========================================

-- Departments
insert into department (name) values
	('IT-Service'),
	('Logistik'),
	('Verwaltung')
on conflict (name) do nothing;

-- Device Types (2-3 gefordert)
insert into device_type (name) values
	('Laptop'),
	('Monitor'),
	('Handscanner')
on conflict (name) do nothing;

-- Locations (2-3 gefordert)
insert into location (name) values
	('Gebaude E'),
	('Gebaude F'),
	('Gebaude H')
on conflict (name) do nothing;

-- Personen (eine Handvoll)
insert into person (personnel_number, first_name, last_name, email, department_id, is_active)
select v.personnel_number, v.first_name, v.last_name, v.email, d.department_id, v.is_active
from (
	values
		('P1001', 'Anna',  'Koch',   'anna.koch@example.org',   'IT-Service', true),
		('P1002', 'Ben',   'Schulz', 'ben.schulz@example.org',  'Logistik',   true),
		('P1003', 'Clara', 'Meier',  'clara.meier@example.org', 'Verwaltung', true),
		('P1004', 'David', 'Nguyen', 'david.nguyen@example.org','IT-Service', true),
		('P1005', 'Eda',   'Yilmaz', 'eda.yilmaz@example.org',  'Logistik',   true)
) as v(personnel_number, first_name, last_name, email, department_name, is_active)
join department d on d.name = v.department_name
on conflict (personnel_number) do nothing;

-- Devices (eine Handvoll, eindeutige Seriennummern)
insert into device (serial_number, inventory_number, device_type_id, location_id, status, is_loanable)
select v.serial_number, v.inventory_number, dt.device_type_id, l.location_id, v.status, v.is_loanable
from (
	values
		('SN-LAP-1001', 'INV-0001', 'Laptop',      'Gebaude E', 'assigned',  true),
		('SN-LAP-1002', 'INV-0002', 'Laptop',      'Gebaude F', 'available', true),
		('SN-MON-2001', 'INV-0003', 'Monitor',     'Gebaude E', 'assigned',  true),
		('SN-HS-3001',  'INV-0004', 'Handscanner', 'Gebaude H', 'assigned',  true),
		('SN-MON-2002', 'INV-0005', 'Monitor',     'Gebaude F', 'available', true)
) as v(serial_number, inventory_number, device_type_name, location_name, status, is_loanable)
join device_type dt on dt.name = v.device_type_name
join location l on l.name = v.location_name
on conflict (serial_number) do nothing;

-- Assignments (eine Handvoll Historie)
insert into assignment (device_id, person_id, assigned_at, due_at, returned_at, note)
select d.device_id, p.person_id, v.assigned_at, v.due_at, v.returned_at, v.note
from (
	values
		('SN-LAP-1001', 'P1001', timestamp '2026-04-08 09:00:00', timestamp '2026-05-08 18:00:00', null, 'Projektarbeit Datenanalyse'),
		('SN-MON-2001', 'P1004', timestamp '2026-04-11 10:30:00', timestamp '2026-05-11 18:00:00', null, 'Arbeitsplatz-Erweiterung'),
		('SN-HS-3001',  'P1002', timestamp '2026-04-03 07:45:00', timestamp '2026-04-23 18:00:00', null, 'Wareneingang Pilot'),
		('SN-LAP-1002', 'P1003', timestamp '2026-03-01 09:15:00', timestamp '2026-03-31 18:00:00', timestamp '2026-03-29 16:00:00', 'Bereits zurueckgegeben')
) as v(serial_number, personnel_number, assigned_at, due_at, returned_at, note)
join device d on d.serial_number = v.serial_number
join person p on p.personnel_number = v.personnel_number
where not exists (
	select 1
	from assignment a
	where a.device_id = d.device_id
	  and a.person_id = p.person_id
	  and a.assigned_at = v.assigned_at
);
