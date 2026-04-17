from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DirectoryEntry, RepertoireItem
from app.db.session import get_engine


def _iso_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _login(client, username: str, password: str):
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


def _switch_context(client, csrf_token: str, context: dict, nonce: str):
    response = client.post(
        "/api/v1/contexts/active",
        headers={
            "X-CSRF-Token": csrf_token,
            "X-Request-Nonce": nonce,
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "organization_id": context["organization_id"],
            "program_id": context["program_id"],
            "event_id": context["event_id"],
            "store_id": context["store_id"],
        },
    )
    assert response.status_code == 200


def test_recommendation_scoring_uses_tag_match_and_weights(client):
    login = _login(client, "admin", "admin123!")
    csrf = login.json()["csrf_token"]

    before = client.get("/api/v1/recommendations/directory", params={"tags": ["jazz"]})
    assert before.status_code == 200
    by_name_before = {item["display_name"]: item for item in before.json()["results"]}
    assert by_name_before["Ava Martinez"]["score"]["tag_match"] > 0

    upsert = client.put(
        "/api/v1/recommendations/config",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "4050fd92-c7bc-4a65-80ff-130823979fd4",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "scope": "event_store",
            "enabled_modes": {
                "popularity_30d": True,
                "recent_activity_72h": True,
                "tag_match": True,
            },
            "weights": {
                "popularity_30d": 0,
                "recent_activity_72h": 0,
                "tag_match": 1,
            },
            "pins_enabled": True,
            "max_pins": 5,
            "pin_ttl_hours": None,
            "enforce_pairing_rules": True,
            "allow_staff_event_store_manage": False,
        },
    )
    assert upsert.status_code == 200

    after = client.get("/api/v1/recommendations/directory", params={"tags": ["jazz"]})
    assert after.status_code == 200
    by_name_after = {item["display_name"]: item for item in after.json()["results"]}
    assert by_name_after["Ava Martinez"]["score"]["total"] > by_name_after["Ben Carter"]["score"]["total"]
    assert by_name_after["Ava Martinez"]["score"]["popularity_30d"] == 0
    assert by_name_after["Ava Martinez"]["score"]["recent_activity_72h"] == 0


def test_runtime_directory_search_signals_increase_recommendation_scores(client):
    with Session(get_engine()) as session:
        scope_seed = session.scalar(select(DirectoryEntry).where(DirectoryEntry.display_name == "Ava Martinez"))
        assert scope_seed is not None
        boosted = DirectoryEntry(
            organization_id=scope_seed.organization_id,
            program_id=scope_seed.program_id,
            event_id=scope_seed.event_id,
            store_id=scope_seed.store_id,
            display_name="Zulu Runtime Boosted",
            stage_name=None,
            region=scope_seed.region,
            email="zulu.runtime.boosted@harmonyhub.example",
            phone="555-111-9898",
            address_line1="901 Runtime Lane",
            biography="runtime ranking proof target",
        )
        control = DirectoryEntry(
            organization_id=scope_seed.organization_id,
            program_id=scope_seed.program_id,
            event_id=scope_seed.event_id,
            store_id=scope_seed.store_id,
            display_name="Alpha Runtime Control",
            stage_name=None,
            region=scope_seed.region,
            email="alpha.runtime.control@harmonyhub.example",
            phone="555-111-9797",
            address_line1="902 Runtime Lane",
            biography="runtime ranking proof control",
        )
        session.add_all([boosted, control])
        session.commit()

    _login(client, "student", "stud123!")

    before = client.get("/api/v1/recommendations/directory")
    assert before.status_code == 200
    before_names = [item["display_name"] for item in before.json()["results"]]
    assert before_names.index("Zulu Runtime Boosted") > before_names.index("Alpha Runtime Control")
    before_scores = {item["display_name"]: item["score"] for item in before.json()["results"]}

    search = client.get("/api/v1/directory/search", params={"actor": "Zulu Runtime Boosted"})
    assert search.status_code == 200
    assert [item["display_name"] for item in search.json()["results"]] == ["Zulu Runtime Boosted"]

    after = client.get("/api/v1/recommendations/directory")
    assert after.status_code == 200
    after_names = [item["display_name"] for item in after.json()["results"]]
    assert after_names.index("Zulu Runtime Boosted") < after_names.index("Alpha Runtime Control")
    after_scores = {item["display_name"]: item["score"] for item in after.json()["results"]}

    assert after_scores["Zulu Runtime Boosted"]["popularity_30d"] > before_scores["Zulu Runtime Boosted"]["popularity_30d"]
    assert (
        after_scores["Zulu Runtime Boosted"]["recent_activity_72h"]
        > before_scores["Zulu Runtime Boosted"]["recent_activity_72h"]
    )


def test_runtime_repertoire_search_signals_increase_recommendation_scores(client):
    with Session(get_engine()) as session:
        scope_seed = session.scalar(select(RepertoireItem).where(RepertoireItem.title == "Moonlight Sonata"))
        assert scope_seed is not None
        boosted = RepertoireItem(
            organization_id=scope_seed.organization_id,
            program_id=scope_seed.program_id,
            event_id=scope_seed.event_id,
            store_id=scope_seed.store_id,
            title="Zulu Runtime Piece",
            composer="Runtime Composer",
        )
        control = RepertoireItem(
            organization_id=scope_seed.organization_id,
            program_id=scope_seed.program_id,
            event_id=scope_seed.event_id,
            store_id=scope_seed.store_id,
            title="Alpha Runtime Piece",
            composer="Runtime Composer",
        )
        session.add_all([boosted, control])
        session.commit()

    _login(client, "student", "stud123!")

    before = client.get("/api/v1/recommendations/repertoire")
    assert before.status_code == 200
    before_titles = [item["title"] for item in before.json()["results"]]
    assert before_titles.index("Zulu Runtime Piece") > before_titles.index("Alpha Runtime Piece")
    before_scores = {item["title"]: item["score"] for item in before.json()["results"]}

    search = client.get("/api/v1/repertoire/search", params={"q": "Zulu Runtime Piece"})
    assert search.status_code == 200
    assert [item["title"] for item in search.json()["results"]] == ["Zulu Runtime Piece"]

    after = client.get("/api/v1/recommendations/repertoire")
    assert after.status_code == 200
    after_titles = [item["title"] for item in after.json()["results"]]
    assert after_titles.index("Zulu Runtime Piece") < after_titles.index("Alpha Runtime Piece")
    after_scores = {item["title"]: item["score"] for item in after.json()["results"]}

    assert after_scores["Zulu Runtime Piece"]["popularity_30d"] > before_scores["Zulu Runtime Piece"]["popularity_30d"]
    assert after_scores["Zulu Runtime Piece"]["recent_activity_72h"] > before_scores["Zulu Runtime Piece"]["recent_activity_72h"]


def test_config_inheritance_and_staff_delegation_boundary(client):
    login = _login(client, "staff", "staff123!")
    csrf = login.json()["csrf_token"]

    event_scope = client.get("/api/v1/recommendations/config", params={"scope": "event_store"})
    assert event_scope.status_code == 200
    event_scope_payload = event_scope.json()
    assert event_scope_payload["id"] is None
    assert event_scope_payload["inherited_from_scope"] == "program"

    upsert_allowed = client.put(
        "/api/v1/recommendations/config",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "faeef4f6-4de5-4fed-9f66-fbdca2ec86ec",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "scope": "event_store",
            "enabled_modes": {
                "popularity_30d": True,
                "recent_activity_72h": True,
                "tag_match": True,
            },
            "weights": {
                "popularity_30d": 0.4,
                "recent_activity_72h": 0.4,
                "tag_match": 0.2,
            },
            "pins_enabled": True,
            "max_pins": 4,
            "pin_ttl_hours": None,
            "enforce_pairing_rules": True,
            "allow_staff_event_store_manage": False,
        },
    )
    assert upsert_allowed.status_code == 200
    assert upsert_allowed.json()["id"] is not None

    contexts = client.get("/api/v1/contexts/available")
    target = next(item for item in contexts.json() if item["event_name"] == "Encore Matinee")
    _switch_context(client, csrf, target, nonce="351f5b0e-2b99-4af7-a8cf-f0bebb7f4dbd")

    upsert_denied = client.put(
        "/api/v1/recommendations/config",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "09e1e17b-bf76-4b7f-90d6-184527809623",
            "X-Request-Timestamp": _iso_now(),
        },
        json={
            "scope": "event_store",
            "enabled_modes": {
                "popularity_30d": True,
                "recent_activity_72h": True,
                "tag_match": True,
            },
            "weights": {
                "popularity_30d": 0.4,
                "recent_activity_72h": 0.4,
                "tag_match": 0.2,
            },
            "pins_enabled": True,
            "max_pins": 4,
            "pin_ttl_hours": None,
            "enforce_pairing_rules": True,
            "allow_staff_event_store_manage": False,
        },
    )
    assert upsert_denied.status_code == 403
    assert upsert_denied.json()["error"]["code"] == "FORBIDDEN"


def test_featured_pin_ordering_prioritizes_newer_pins(client):
    login = _login(client, "admin", "admin123!")
    csrf = login.json()["csrf_token"]

    directory = client.get("/api/v1/directory/search")
    entries = {entry["display_name"]: entry["id"] for entry in directory.json()["results"]}
    ava_id = entries["Ava Martinez"]

    first_before = client.get("/api/v1/recommendations/directory").json()["results"][0]
    assert first_before["pinned"] is True

    pin_ava = client.post(
        f"/api/v1/recommendations/featured/{ava_id}",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "5c252d61-c6d7-49f3-bbb8-75edb16b89df",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"surface": "directory"},
    )
    assert pin_ava.status_code == 200

    first_after = client.get("/api/v1/recommendations/directory").json()["results"][0]
    assert first_after["entry_id"] == ava_id
    assert first_after["pinned"] is True


def test_blocklist_overrides_allowlist_in_recommendations(client):
    login = _login(client, "admin", "admin123!")
    csrf = login.json()["csrf_token"]

    directory = client.get("/api/v1/directory/search")
    entries = {entry["display_name"]: entry["id"] for entry in directory.json()["results"]}
    repertoire = client.get("/api/v1/repertoire/search")
    items = {item["title"]: item["id"] for item in repertoire.json()["results"]}

    ava_id = entries["Ava Martinez"]
    moonlight_id = items["Moonlight Sonata"]

    allow = client.post(
        "/api/v1/pairing-rules/allowlist",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "d4e4a11a-c079-4597-a194-f6a5e247f80e",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"directory_entry_id": ava_id, "repertoire_item_id": moonlight_id, "note": "allow ava moonlight"},
    )
    assert allow.status_code == 200

    block = client.post(
        "/api/v1/pairing-rules/blocklist",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "a1f5773a-e5a9-4064-aa17-9f23d4f86fa6",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"directory_entry_id": ava_id, "repertoire_item_id": moonlight_id, "note": "block wins"},
    )
    assert block.status_code == 200

    recommended = client.get("/api/v1/recommendations/directory", params={"repertoire_item_id": moonlight_id})
    assert recommended.status_code == 200
    names = {item["display_name"] for item in recommended.json()["results"]}
    assert "Ava Martinez" not in names


def test_directory_recommendations_preserve_masked_contact(client):
    _login(client, "student", "stud123!")
    response = client.get("/api/v1/recommendations/directory")
    assert response.status_code == 200
    assert response.json()["results"]
    contact = response.json()["results"][0]["contact"]
    assert contact["masked"] is True
    assert contact["address_line1"] == "*** Hidden address ***"


def test_recommendation_support_endpoints_cover_effective_validate_repertoire_and_cleanup(client):
    login = _login(client, "admin", "admin123!")
    csrf = login.json()["csrf_token"]

    validate = client.post(
        "/api/v1/recommendations/config/validate",
        json={
            "scope": "event_store",
            "enabled_modes": {
                "popularity_30d": True,
                "recent_activity_72h": True,
                "tag_match": True,
            },
            "weights": {
                "popularity_30d": 5,
                "recent_activity_72h": 3,
                "tag_match": 2,
            },
            "pins_enabled": True,
            "max_pins": 3,
            "pin_ttl_hours": None,
            "enforce_pairing_rules": True,
            "allow_staff_event_store_manage": False,
        },
    )
    assert validate.status_code == 200
    normalized = validate.json()["normalized_weights"]
    assert normalized == {"popularity_30d": 0.5, "recent_activity_72h": 0.3, "tag_match": 0.2}

    effective = client.get("/api/v1/recommendations/config/effective")
    assert effective.status_code == 200
    assert effective.json()["scope"]["scope"] in {"event_store", "program", "organization"}

    directory = client.get("/api/v1/directory/search")
    assert directory.status_code == 200
    ava_id = next(entry["id"] for entry in directory.json()["results"] if entry["display_name"] == "Ava Martinez")

    repertoire = client.get("/api/v1/repertoire/search")
    assert repertoire.status_code == 200
    moonlight_id = next(item["id"] for item in repertoire.json()["results"] if item["title"] == "Moonlight Sonata")

    recommended = client.get(
        "/api/v1/recommendations/repertoire",
        params={"directory_entry_id": ava_id, "tags": ["classical"], "limit": 5},
    )
    assert recommended.status_code == 200
    recommended_payload = recommended.json()
    assert recommended_payload["results"]
    assert recommended_payload["results"][0]["score"]["total"] >= 0

    list_featured_before = client.get("/api/v1/recommendations/featured", params={"surface": "directory"})
    assert list_featured_before.status_code == 200

    pin = client.post(
        f"/api/v1/recommendations/featured/{ava_id}",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "coverage-pin-directory",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"surface": "directory"},
    )
    assert pin.status_code == 200

    list_featured_after = client.get("/api/v1/recommendations/featured", params={"surface": "directory"})
    assert list_featured_after.status_code == 200
    assert any(row["directory_entry_id"] == ava_id for row in list_featured_after.json())

    unpin = client.delete(
        f"/api/v1/recommendations/featured/{ava_id}",
        params={"surface": "directory"},
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "coverage-unpin-directory",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert unpin.status_code == 200

    allow = client.post(
        "/api/v1/pairing-rules/allowlist",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "coverage-allow-rule",
            "X-Request-Timestamp": _iso_now(),
        },
        json={"directory_entry_id": ava_id, "repertoire_item_id": moonlight_id, "note": "coverage allow"},
    )
    assert allow.status_code == 200
    allow_id = allow.json()["id"]

    list_allow = client.get("/api/v1/pairing-rules", params={"effect": "allow"})
    assert list_allow.status_code == 200
    assert any(rule["id"] == allow_id for rule in list_allow.json())

    deleted = client.delete(
        f"/api/v1/pairing-rules/{allow_id}",
        headers={
            "X-CSRF-Token": csrf,
            "X-Request-Nonce": "coverage-delete-rule",
            "X-Request-Timestamp": _iso_now(),
        },
    )
    assert deleted.status_code == 200
