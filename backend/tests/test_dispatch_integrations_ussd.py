from .conftest import add_hospital, available, make_staff

KUMASI = {"lat": 6.69, "lng": -1.62}


def dispatcher(client, db):
    agency = db.execute("insert into agencies (name) values ('NAS Ashanti') returning id::text").fetchone()[0]
    return make_staff(client, db, "controller@nas.gh", "dispatcher", agency_id=agency)


def test_dispatch_needs_dispatcher_role(client, db):
    hid = add_hospital(db, "Hosp H")
    nurse = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=hid)
    r = client.post("/v1/dispatch/holds", headers=nurse,
                    json={**KUMASI, "severity": "severe", "condition_category": "road_accident"})
    assert r.status_code == 403


def test_dispatch_prefers_fresh_then_nearest_and_forces_er_for_critical(client, db):
    near_stale = add_hospital(db, "Near but stale", lat=6.691, lng=-1.621)
    far_fresh = add_hospital(db, "Farther, fresh", lat=6.75, lng=-1.60)
    db.execute("update wards set updated_at = now() - interval '5 hours' where hospital_id = %s", (near_stale,))
    headers = dispatcher(client, db)
    opts = client.get("/v1/dispatch/options", params={**KUMASI, "severity": "critical", "ward": "general"}, headers=headers).json()
    assert [o["hospital_name"] for o in opts] == ["Farther, fresh", "Near but stale"]
    assert opts[0]["ward"] == "ER"
    assert {"lat", "lng"} <= set(opts[0])  # for the dispatch map
    hold = client.post("/v1/dispatch/holds", headers=headers,
                       json={**KUMASI, "severity": "critical", "ward": "general", "condition_category": "road_accident"}).json()
    assert hold["hospital_id"] == far_fresh and hold["ward"] == "ER" and hold["eta_minutes"] >= 5
    assert hold["hospital_lat"] == 6.75 and hold["hospital_lng"] == -1.60
    board = client.get("/v1/dispatch/holds", headers=headers).json()
    assert board[0]["hospital_lat"] == 6.75


def test_decline_reroutes_dispatcher_hold(client, db):
    first = add_hospital(db, "First", lat=6.691, lng=-1.621)
    second = add_hospital(db, "Second", lat=6.72, lng=-1.60)
    headers = dispatcher(client, db)
    hold = client.post("/v1/dispatch/holds", headers=headers,
                       json={**KUMASI, "severity": "severe", "condition_category": "chest_pain"}).json()
    assert hold["hospital_id"] == first
    nurse = make_staff(client, db, "nurse@first.gh", "hospital_staff", hospital_id=first)
    r = client.post(f"/v1/hospital/{first}/holds/{hold['id']}/decline", headers=nurse, json={"reason": "No oxygen"}).json()
    assert r["hold"]["status"] == "declined"
    assert r["rerouted_to"]["hospital_id"] == second
    assert r["rerouted_to"]["previous_hold_id"] == hold["id"]
    board = client.get("/v1/dispatch/holds", headers=headers).json()
    assert [h["hospital_id"] for h in board] == [second]
    # Second declines too: nowhere left that hasn't already said no.
    nurse2 = make_staff(client, db, "nurse@second.gh", "hospital_staff", hospital_id=second)
    r2 = client.post(f"/v1/hospital/{second}/holds/{r['rerouted_to']['id']}/decline", headers=nurse2).json()
    assert r2["rerouted_to"] is None


def test_api_key_lifecycle(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (10, 5)})
    other = add_hospital(db, "Other")
    admin = make_staff(client, db, "admin@h.gh", "hospital_admin", hospital_id=hid)
    nurse = make_staff(client, db, "nurse@h.gh", "hospital_staff", hospital_id=hid)
    assert client.post(f"/v1/hospital/{hid}/api-keys", headers=nurse, json={"label": "HIS"}).status_code == 403

    created = client.post(f"/v1/hospital/{hid}/api-keys", headers=admin,
                          json={"label": "HIS", "scopes": ["beds:write"]}).json()
    key = {"Authorization": f"Bearer {created['key']}"}
    assert created["key"].startswith(f"ba_live_{created['prefix']}_")
    assert db.execute("select key_hash from api_keys").fetchone()[0] != created["key"]
    listed = client.get(f"/v1/hospital/{hid}/api-keys", headers=admin).json()
    assert "key" not in listed[0] and "key_hash" not in listed[0]

    assert client.put("/v1/integrations/wards/ER", headers=key, json={"occupied": 9}).status_code == 200
    assert available(client, hid, "ER") == 1
    assert available(client, other, "ER") == 2  # untouched
    assert client.get("/v1/integrations/holds", headers=key).status_code == 403  # missing scope
    bad = {"Authorization": created["key"][:-1] + ("A" if created["key"][-1] != "A" else "B")}
    assert client.put("/v1/integrations/wards/ER", headers={"Authorization": "Bearer " + bad["Authorization"]},
                      json={"occupied": 1}).status_code == 401

    client.delete(f"/v1/hospital/{hid}/api-keys/{created['id']}", headers=admin)
    assert client.put("/v1/integrations/wards/ER", headers=key, json={"occupied": 1}).status_code == 401


def test_integration_accepts_hold(client, db):
    hid = add_hospital(db, "Hosp H")
    admin = make_staff(client, db, "admin@h.gh", "hospital_admin", hospital_id=hid)
    key = {"Authorization": "Bearer " + client.post(f"/v1/hospital/{hid}/api-keys", headers=admin, json={"label": "HIS"}).json()["key"]}
    headers = dispatcher(client, db)
    hold = client.post("/v1/dispatch/holds", headers=headers,
                       json={**KUMASI, "severity": "moderate", "condition_category": "bleeding_injury"}).json()
    assert [h["id"] for h in client.get("/v1/integrations/holds", headers=key).json()] == [hold["id"]]
    assert client.post(f"/v1/integrations/holds/{hold['id']}/accept", headers=key).json()["hold"]["status"] == "accepted"


# ---------------------------------------------------------------- USSD


def ussd(client, text, phone="+233241234567", key="dev-ussd-secret"):
    r = client.post(f"/v1/ussd?key={key}", data={"sessionId": "s1", "serviceCode": "*920*1#", "phoneNumber": phone, "text": text})
    return r.status_code, r.text


def test_ussd_requires_secret(client, db):
    assert ussd(client, "", key="wrong")[0] == 403


def test_ussd_full_emergency_flow(client, db):
    hid = add_hospital(db, "Komfo Anokye", wards={"ER": (5, 3)})
    add_hospital(db, "Tamale Teaching", region="Northern", lat=9.39, lng=-0.84)
    status, text = ussd(client, "")
    assert status == 200 and text.startswith("CON ") and "1. Emergency" in text
    assert ussd(client, "1")[1] == "CON Your region:\n1. Ashanti\n2. Northern\n0. Start again"
    text = ussd(client, "1*1")[1]
    assert "1. Komfo Anokye 2 free" in text
    assert "What is the problem?" in ussd(client, "1*1*1")[1]
    status, text = ussd(client, "1*1*1*1")
    assert text.startswith("END Bed held at Komfo Anokye. Code ")
    assert available(client, hid, "ER") == 1
    row = db.execute("select source, citizen_phone, condition_category from holds").fetchone()
    assert row == ("ussd", "+233241234567", "chest_pain")
    # Dialling again doesn't take a second bed.
    assert "already have a bed held" in ussd(client, "1*1*1*1")[1]
    assert available(client, hid, "ER") == 1


def test_ussd_restart_and_invalid(client, db):
    add_hospital(db, "Hosp H")
    assert "Your region" in ussd(client, "2*1*0*1")[1]  # 0 restarts; then '1' = Emergency
    assert ussd(client, "7")[1].startswith("END Invalid choice")


def test_ussd_paging(client, db):
    for i in range(6):
        add_hospital(db, f"Hosp {i}")
    first = ussd(client, "1*1")[1]
    assert "98. More" in first and first.count(" free") == 4
    second = ussd(client, "1*1*98")[1]
    assert second.count(" free") == 2 and "98. More" not in second
