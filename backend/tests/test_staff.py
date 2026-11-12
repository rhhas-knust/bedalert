from .conftest import add_hospital, available, citizen_headers, make_staff, staff_headers


def test_staff_routes_need_a_staff_token(client, db):
    hid = add_hospital(db, "Hosp H")
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 1}).status_code == 401
    # a citizen token is not a staff token
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 1}, headers=citizen_headers(client)).status_code == 401


def test_staff_can_only_touch_their_own_hospital(client, db):
    mine = add_hospital(db, "Mine")
    other = add_hospital(db, "Other")
    headers = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=mine)
    assert client.put(f"/v1/hospital/{mine}/wards/ER", json={"free": 4}, headers=headers).status_code == 200
    assert client.put(f"/v1/hospital/{other}/wards/ER", json={"free": 4}, headers=headers).status_code == 403
    assert client.get(f"/v1/hospital/{other}", headers=headers).status_code == 403


def test_bed_update_semantics_and_audit(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (10, 5)})
    headers = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=hid)
    assert available(client, hid, "ER") == 5
    client.put(f"/v1/hospital/{hid}/wards/ER", json={"free_delta": 1}, headers=headers)
    assert available(client, hid, "ER") == 6
    client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 2}, headers=headers)
    assert available(client, hid, "ER") == 2
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 11}, headers=headers).status_code == 422
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 1, "occupied": 1}, headers=headers).status_code == 422
    # staff cannot change the number of beds; admins can
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"total": 20}, headers=headers).status_code == 403
    assert db.execute("select count(*) from audit_log where action = 'ward.updated'").fetchone()[0] == 2


def test_held_beds_count_as_physically_free(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (10, 5)})
    client.post("/v1/holds", headers=citizen_headers(client),
                json={"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain"})
    headers = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=hid)
    # Nurse sees 5 empty beds (one is kept for the incoming patient).
    client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 5}, headers=headers)
    assert available(client, hid, "ER") == 4


def test_accept_and_arrive(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (10, 5)})
    hold = client.post("/v1/holds", headers=citizen_headers(client),
                       json={"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain",
                             "condition_note": "Grandfather, 70"}).json()
    headers = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=hid)
    incoming = client.get(f"/v1/hospital/{hid}/holds", headers=headers).json()
    assert incoming[0]["condition_note"] == "Grandfather, 70"  # visible to the receiving hospital only
    assert client.post(f"/v1/hospital/{hid}/holds/{hold['id']}/accept", headers=headers).json()["hold"]["status"] == "accepted"
    assert client.post(f"/v1/hospital/{hid}/holds/{hold['id']}/accept", headers=headers).status_code == 409
    assert client.post(f"/v1/hospital/{hid}/holds/{hold['id']}/arrive", headers=headers).json()["hold"]["status"] == "arrived"
    # hold is closed and the patient now occupies a bed: 10 - 6 = 4
    assert available(client, hid, "ER") == 4


def test_other_hospital_cannot_act_on_hold(client, db):
    a = add_hospital(db, "Hosp A")
    b = add_hospital(db, "Hosp B")
    hold = client.post("/v1/holds", headers=citizen_headers(client),
                       json={"hospital_id": a, "type": "emergency", "condition_category": "chest_pain"}).json()
    headers_b = make_staff(client, db, "nurse@b.gh", "hospital_staff", hospital_id=b)
    assert client.post(f"/v1/hospital/{b}/holds/{hold['id']}/decline", headers=headers_b).status_code == 404


def test_apply_verify_goes_live(client, db):
    applicant = staff_headers(client, "boss@newclinic.gh")
    r = client.post("/v1/hospitals/apply", headers=applicant, json={
        "name": "New Clinic", "region": "Northern", "district": "Tamale Metro", "city": "Tamale",
        "lat": 9.4, "lng": -0.85, "license_number": "HEFRA-123", "phone": "0372000000",
        "wards": [{"kind": "ER", "total": 4, "occupied": 1}],
    })
    assert r.status_code == 201 and r.json()["status"] == "pending"
    hid = r.json()["id"]
    assert client.get("/v1/facilities").json() == []
    # applicant is admin of their pending hospital but cannot verify it
    assert client.get("/v1/me", headers=applicant).json()["hospitals"][0]["role"] == "hospital_admin"
    assert client.post(f"/v1/admin/hospitals/{hid}/verify", headers=applicant).status_code == 403
    # nor create API keys before verification
    assert client.post(f"/v1/hospital/{hid}/api-keys", headers=applicant, json={"label": "HIS"}).status_code == 409

    admin = make_staff(client, db, "ops@bedalert.gh", "network_admin")
    assert client.post(f"/v1/admin/hospitals/{hid}/verify", headers=admin).json()["status"] == "verified"
    assert [f["name"] for f in client.get("/v1/facilities").json()] == ["New Clinic"]


def test_hospital_admin_adds_colleague(client, db):
    hid = add_hospital(db, "Hosp H")
    admin = make_staff(client, db, "admin@h.gh", "hospital_admin", hospital_id=hid)
    assert client.post(f"/v1/hospital/{hid}/members", headers=admin, json={"email": "new@h.gh"}).status_code == 404
    newbie = staff_headers(client, "new@h.gh")
    client.get("/v1/me", headers=newbie)  # signs in once
    assert client.post(f"/v1/hospital/{hid}/members", headers=admin, json={"email": "new@h.gh"}).status_code == 201
    assert client.put(f"/v1/hospital/{hid}/wards/ER", json={"free": 1}, headers=newbie).status_code == 200
