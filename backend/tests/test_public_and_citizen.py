from .conftest import add_hospital, available, citizen_headers


def test_public_list_hides_unverified_and_private_fields(client, db):
    live = add_hospital(db, "Live Hospital")
    add_hospital(db, "Pending Hospital", status="pending")
    body = client.get("/v1/facilities").json()
    assert [f["name"] for f in body] == ["Live Hospital"]
    f = body[0]
    assert f["id"] == live
    assert set(f) == {"id", "name", "region", "district", "city", "lat", "lng", "phone", "wards"}
    assert set(f["wards"][0]) == {"kind", "total", "available", "updated_at", "updated_minutes_ago", "fresh"}


def test_public_sorted_by_distance(client, db):
    add_hospital(db, "Far", lat=9.39, lng=-0.84)
    add_hospital(db, "Near", lat=6.70, lng=-1.63)
    names = [f["name"] for f in client.get("/v1/facilities?lat=6.69&lng=-1.62").json()]
    assert names == ["Near", "Far"]


def test_old_insecure_routes_are_gone(client, db):
    assert client.get("/api/bookings").status_code == 404
    assert client.get("/api/hospitals").status_code == 404


def test_otp_wrong_code_and_rate_limit(client, db):
    r = client.post("/v1/auth/otp/request", json={"phone": "024 123 4567"})
    assert r.status_code == 200 and r.json()["phone"] == "+233241234567"
    assert client.post("/v1/auth/otp/verify", json={"phone": "0241234567", "code": "000000" if r.json()["dev_code"] != "000000" else "111111"}).status_code == 400
    # the failed attempt is recorded
    assert db.execute("select attempts from otp_codes").fetchone()[0] == 1
    client.post("/v1/auth/otp/request", json={"phone": "0241234567"})
    client.post("/v1/auth/otp/request", json={"phone": "0241234567"})
    assert client.post("/v1/auth/otp/request", json={"phone": "0241234567"}).status_code == 429


def test_hold_requires_verified_phone(client, db):
    hid = add_hospital(db, "Hosp H")
    r = client.post("/v1/holds", json={"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain"})
    assert r.status_code == 401


def test_citizen_hold_reduces_availability_and_sms_is_queued(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (5, 3)})
    headers = citizen_headers(client)
    assert available(client, hid, "ER") == 2
    r = client.post("/v1/holds", headers=headers,
                    json={"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain"})
    assert r.status_code == 201, r.text
    hold = r.json()
    assert hold["ward"] == "ER" and hold["status"] == "held" and len(hold["code"]) == 6
    assert "citizen_phone" not in hold
    assert available(client, hid, "ER") == 1
    purposes = {row[0] for row in db.execute("select purpose from sms_outbox")}
    assert {"otp", "hold_citizen", "hold_hospital"} <= purposes


def test_one_active_hold_per_phone_then_cancel(client, db):
    hid = add_hospital(db, "Hosp H", wards={"general": (10, 0)})
    headers = citizen_headers(client)
    body = {"hospital_id": hid, "type": "stable", "condition_category": "referral"}
    first = client.post("/v1/holds", headers=headers, json=body)
    assert first.status_code == 201
    second = client.post("/v1/holds", headers=headers, json=body)
    assert second.status_code == 409 and "already have" in second.json()["detail"]
    assert available(client, hid, "general") == 9

    cancel = client.post(f"/v1/holds/{first.json()['id']}/cancel", headers=headers)
    assert cancel.status_code == 200 and cancel.json()["status"] == "cancelled"
    assert available(client, hid, "general") == 10
    assert client.post("/v1/holds", headers=headers, json=body).status_code == 201


def test_cannot_cancel_someone_elses_hold(client, db):
    hid = add_hospital(db, "Hosp H")
    mine = client.post("/v1/holds", headers=citizen_headers(client, "0241111111"),
                       json={"hospital_id": hid, "type": "stable", "condition_category": "referral"}).json()
    other = citizen_headers(client, "0242222222")
    assert client.post(f"/v1/holds/{mine['id']}/cancel", headers=other).status_code == 404


def test_last_bed_cannot_be_taken_twice(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (1, 0)})
    body = {"hospital_id": hid, "type": "emergency", "condition_category": "road_accident"}
    assert client.post("/v1/holds", headers=citizen_headers(client, "0241111111"), json=body).status_code == 201
    r = client.post("/v1/holds", headers=citizen_headers(client, "0242222222"), json=body)
    assert r.status_code == 409 and "No ER beds" in r.json()["detail"]


def test_expired_hold_releases_bed(client, db):
    hid = add_hospital(db, "Hosp H", wards={"ER": (1, 0)})
    client.post("/v1/holds", headers=citizen_headers(client),
                json={"hospital_id": hid, "type": "emergency", "condition_category": "labour"})
    assert available(client, hid, "ER") == 0
    db.execute("update holds set expires_at = now() - interval '1 minute'")
    assert available(client, hid, "ER") == 1
    assert db.execute("select status from holds").fetchone()[0] == "expired"


def test_stable_booking_cannot_take_er_bed(client, db):
    hid = add_hospital(db, "Hosp H")
    r = client.post("/v1/holds", headers=citizen_headers(client),
                    json={"hospital_id": hid, "type": "stable", "ward": "ER", "condition_category": "referral"})
    assert r.status_code == 422


def test_pending_hospital_cannot_receive_holds(client, db):
    hid = add_hospital(db, "Unverified", status="pending")
    r = client.post("/v1/holds", headers=citizen_headers(client),
                    json={"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain"})
    assert r.status_code == 404


def test_malformed_ids_are_404_not_500(client, db):
    assert client.get("/v1/facilities/not-a-uuid").status_code == 404


def test_last_bed_under_real_concurrency(client, db):
    """20 people press 'hold' on the last bed at the same moment: exactly one wins."""
    from concurrent.futures import ThreadPoolExecutor

    hid = add_hospital(db, "Hosp H", wards={"ER": (1, 0)})
    tokens = [citizen_headers(client, f"02400000{i:02d}") for i in range(20)]
    body = {"hospital_id": hid, "type": "emergency", "condition_category": "chest_pain"}
    with ThreadPoolExecutor(max_workers=20) as pool:
        codes = list(pool.map(lambda h: client.post("/v1/holds", headers=h, json=body).status_code, tokens))
    assert sorted(codes) == [201] + [409] * 19
    assert db.execute("select count(*) from holds").fetchone()[0] == 1
