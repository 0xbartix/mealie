import pytest
from fastapi.testclient import TestClient

from mealie.schema.diet.tracking import DietOffProduct
from mealie.services.diet import off_client
from mealie.services.diet.off_client import OffUnavailable
from tests.integration_tests.user_household_tests.test_household_diet import (
    PREVIEW,
    SAVE,
    configure,
    recipe_md,
    upload,
)
from tests.utils.fixture_schemas import TestUser

BASE = "/api/households/diet"
MILK = DietOffProduct(
    code="5900512320359",
    name="Mleko 3,2%",
    brand="Mlekovita",
    unit="ml",
    kcal=60,
    protein=3.2,
    fat=3.2,
    carbs=4.7,
    portion_name="1 szklanka",
    portion_grams=250,
)
SKYR = DietOffProduct(
    code="2004331004513", name="Skyr naturalny", brand="Piątnica", kcal=64, protein=12, fat=0, carbs=4
)


class FakeOff:
    def __init__(self) -> None:
        self.down = False
        self.searches: list[str] = []

    def search(self, query: str) -> list[DietOffProduct]:
        if self.down:
            raise OffUnavailable("rate limited")
        self.searches.append(query)
        return [MILK, SKYR]

    def by_barcode(self, code: str) -> DietOffProduct | None:
        return {MILK.code: MILK, SKYR.code: SKYR}.get(code)


@pytest.fixture
def fake_off(monkeypatch):
    fake = FakeOff()
    monkeypatch.setattr(off_client, "_client", fake)
    return fake


def product(api_client: TestClient, user: TestUser, name: str, kcal: float, p: float, f: float, c: float, **extra):
    payload = {"name": name, "kcal": kcal, "protein": p, "fat": f, "carbs": c, **extra}
    response = api_client.post(f"{BASE}/products", json=payload, headers=user.token)
    assert response.status_code == 201, response.text
    return response.json()


def gulasz(api_client: TestClient, user: TestUser) -> dict:
    name = f"Gulasz zamrażarka {user.user_id}"
    result = upload(api_client, user, {"g.md": recipe_md(name, "obiad", 580, 40, 20, 60).encode()}).json()["results"][0]
    assert result["status"] in ("created", "updated")
    options = api_client.get(f"{BASE}/recipes", headers=user.token).json()
    return next(o for o in options if o["slug"] == result["recipeSlug"])


def test_products_crud_search_and_barcode(api_client: TestClient, unique_user: TestUser, h2_user: TestUser, fake_off):
    rice = product(api_client, unique_user, "Ryż biały", 130, 2.7, 0.3, 28, brand="Kupiec")
    assert rice["source"] == "custom"

    listed = api_client.get(f"{BASE}/products", params={"search": "ryz kupiec"}, headers=unique_user.token).json()
    assert [p["id"] for p in listed] == [rice["id"]]
    # other households don't see it
    assert api_client.get(f"{BASE}/products", headers=h2_user.token).json() == []

    found = api_client.get(f"{BASE}/products/search", params={"q": "mleko"}, headers=unique_user.token).json()
    assert [p["code"] for p in found["off"]] == [MILK.code, SKYR.code]
    assert found["offUnavailable"] is False

    saved = api_client.post(f"{BASE}/products/off/{MILK.code}", headers=unique_user.token).json()
    assert (saved["source"], saved["offCode"], saved["unit"], saved["portionGrams"]) == ("off", MILK.code, "ml", 250)
    again = api_client.post(f"{BASE}/products/off/{MILK.code}", headers=unique_user.token).json()
    assert again["id"] == saved["id"]  # no duplicates

    # once saved, it's no longer offered from Open Food Facts
    found = api_client.get(f"{BASE}/products/search", params={"q": "mleko"}, headers=unique_user.token).json()
    assert [p["code"] for p in found["off"]] == [SKYR.code]
    assert [p["id"] for p in found["local"]] == [saved["id"]]

    by_code = api_client.get(f"{BASE}/products/barcode/{SKYR.code}", headers=unique_user.token)
    assert by_code.status_code == 200 and by_code.json()["name"] == "Skyr naturalny"
    assert api_client.get(f"{BASE}/products/barcode/0000000000", headers=unique_user.token).status_code == 404
    assert api_client.get(f"{BASE}/products/barcode/abc", headers=unique_user.token).status_code == 400

    fake_off.down = True
    found = api_client.get(f"{BASE}/products/search", params={"q": "ryż"}, headers=unique_user.token).json()
    assert found["offUnavailable"] is True and [p["id"] for p in found["local"]] == [rice["id"]]

    updated = api_client.put(
        f"{BASE}/products/{rice['id']}",
        json={"name": "Ryż basmati", "kcal": 350, "protein": 8, "fat": 1, "carbs": 77},
        headers=unique_user.token,
    )
    assert updated.status_code == 200 and updated.json()["name"] == "Ryż basmati"
    assert (
        api_client.put(
            f"{BASE}/products/{rice['id']}", json={"name": "X", "kcal": 1}, headers=h2_user.token
        ).status_code
        == 404
    )
    assert api_client.delete(f"{BASE}/products/{rice['id']}", headers=unique_user.token).status_code == 204


def test_freezer_batch_with_changes_and_molds(api_client: TestClient, unique_user: TestUser):
    recipe = gulasz(api_client, unique_user)
    cheese = product(api_client, unique_user, "Ser żółty", 350, 25, 27, 1)
    rice = product(api_client, unique_user, "Ryż", 130, 2.7, 0.3, 28)
    groats = product(api_client, unique_user, "Kasza gryczana", 92, 3.4, 0.6, 19.9)
    request = {
        "recipeId": recipe["id"],
        "frozenOn": "2026-10-16",
        "servings": 6,
        "modifications": [
            {"kind": "add", "productId": cheese["id"], "grams": 50},
            {
                "kind": "swap",
                "productId": groats["id"],
                "grams": 200,
                "replacedProductId": rice["id"],
                "replacedGrams": 200,
            },
        ],
        "molds": [{"capacityMl": 500, "count": 4}, {"capacityMl": 250, "count": 2}],
        "note": "mniej soli",
    }
    preview = api_client.post(f"{BASE}/freezer/preview", json=request, headers=unique_user.token).json()
    assert preview["base"]["kcal"] == 3480
    assert [m["deltaKcal"] for m in preview["modifications"]] == [175, -76]
    assert preview["modifications"][1]["replacedName"] == "Ryż"
    assert preview["total"]["kcal"] == 3480 + 175 - 76
    big, small = preview["molds"]
    assert big["kcal"] == pytest.approx(2 * small["kcal"], abs=0.2)
    assert 4 * big["kcal"] + 2 * small["kcal"] == pytest.approx(preview["total"]["kcal"], abs=1)

    created = api_client.post(f"{BASE}/freezer", json=request, headers=unique_user.token)
    assert created.status_code == 201, created.text
    batch = created.json()
    assert (batch["moldsLeft"], batch["moldsTotal"], batch["note"]) == (6, 6, "mniej soli")
    assert batch["recipeName"] == recipe["name"]

    adjusted = api_client.post(
        f"{BASE}/freezer/{batch['id']}/adjust", json={"moldIndex": 1, "delta": -2}, headers=unique_user.token
    ).json()
    assert adjusted["moldsLeft"] == 4
    too_many = api_client.post(
        f"{BASE}/freezer/{batch['id']}/adjust", json={"moldIndex": 1, "delta": -1}, headers=unique_user.token
    )
    assert too_many.status_code == 400

    listed = api_client.get(f"{BASE}/freezer", headers=unique_user.token).json()
    assert batch["id"] in [b["id"] for b in listed]

    override = {**request, "override": {"kcal": 3000, "protein": 200, "fat": 100, "carbs": 300}}
    preview = api_client.post(f"{BASE}/freezer/preview", json=override, headers=unique_user.token).json()
    assert preview["total"]["kcal"] == 3000

    bad = {**request, "modifications": [{"kind": "swap", "productId": groats["id"], "grams": 100}]}
    assert api_client.post(f"{BASE}/freezer/preview", json=bad, headers=unique_user.token).status_code == 422


def test_diary_adds_every_kind_and_tracks_freezer(api_client: TestClient, unique_user: TestUser, h2_user: TestUser):
    settings = configure(api_client, unique_user)
    bartek = settings["persons"][0]["id"]
    recipe = gulasz(api_client, unique_user)
    oats = product(api_client, unique_user, "Płatki owsiane", 370, 13, 7, 60, portionName="1 garść", portionGrams=40)
    batch = api_client.post(
        f"{BASE}/freezer",
        json={
            "recipeId": recipe["id"],
            "frozenOn": "2026-10-16",
            "servings": 4,
            "molds": [{"capacityMl": 500, "count": 4}],
        },
        headers=unique_user.token,
    ).json()
    day = "2026-10-17"
    base = {"personId": bartek, "date": day}

    def add(**payload):
        response = api_client.post(f"{BASE}/diary", json={**base, **payload}, headers=unique_user.token)
        assert response.status_code == 201, response.text
        return response.json()

    grams = add(mealType="breakfast", kind="product", productId=oats["id"], amount=50, amountUnit="g")
    assert (grams["kcal"], grams["protein"]) == (185, 6.5)
    portion = add(mealType="breakfast", kind="product", productId=oats["id"], amount=2, amountUnit="portion")
    assert portion["kcal"] == 296  # 2 × 40 g
    assert portion["name"] == "Płatki owsiane (1 garść = 40 g)"
    milk = product(api_client, unique_user, "Mleko", 60, 3.2, 3.2, 4.7, unit="ml")
    drink = add(date="2026-10-18", mealType="snack", kind="product", productId=milk["id"], amount=250, amountUnit="g")
    assert (drink["amountUnit"], drink["kcal"], drink["name"]) == ("ml", 150, "Mleko")
    meal = add(mealType="lunch", kind="recipe", recipeId=recipe["id"], amount=1.5)
    assert meal["kcal"] == 870
    frozen = add(mealType="dinner", kind="freezer", batchId=batch["id"], moldIndex=0, amount=1.5)
    assert frozen["kcal"] == 870 and frozen["amountUnit"] == "mold"
    quick = add(mealType="snack", kind="quick", name="Ciastko w pracy", kcal=200, fat=10)
    assert (quick["name"], quick["kcal"], quick["fat"], quick["carbs"]) == ("Ciastko w pracy", 200, 10, 0)

    freezer = {b["id"]: b for b in api_client.get(f"{BASE}/freezer", headers=unique_user.token).json()}
    assert freezer[batch["id"]]["moldsLeft"] == 2.5

    day_view = api_client.get(
        f"{BASE}/diary", params={"person_id": bartek, "date": day}, headers=unique_user.token
    ).json()
    assert len(day_view["entries"]) == 5
    assert day_view["totals"]["kcal"] == 185 + 296 + 870 + 870 + 200
    assert day_view["target"]["kcal"] == 2500

    # eating more molds than are left is refused; halves only
    over = api_client.post(
        f"{BASE}/diary",
        json={**base, "mealType": "dinner", "kind": "freezer", "batchId": batch["id"], "moldIndex": 0, "amount": 3},
        headers=unique_user.token,  # fmt: skip
    )
    assert over.status_code == 400
    third = api_client.post(
        f"{BASE}/diary",
        json={**base, "mealType": "dinner", "kind": "freezer", "batchId": batch["id"], "moldIndex": 0, "amount": 0.3},
        headers=unique_user.token,  # fmt: skip
    )
    assert third.status_code == 400

    # deleting the entry puts the molds back
    assert api_client.delete(f"{BASE}/diary/{frozen['id']}", headers=unique_user.token).status_code == 204
    freezer = {b["id"]: b for b in api_client.get(f"{BASE}/freezer", headers=unique_user.token).json()}
    assert freezer[batch["id"]]["moldsLeft"] == 4

    # other households can't read or delete it; unknown persons are refused
    assert api_client.delete(f"{BASE}/diary/{quick['id']}", headers=h2_user.token).status_code == 404
    unknown = api_client.get(f"{BASE}/diary", params={"person_id": "nobody", "date": day}, headers=unique_user.token)
    assert unknown.status_code == 404


def test_diary_from_plan_uses_each_persons_portions_once(api_client: TestClient, unique_user: TestUser):
    from tests.integration_tests.user_household_tests.test_household_diet import seed_recipes

    seed_recipes(api_client, unique_user)
    settings = configure(api_client, unique_user)
    bartek, ania = (p["id"] for p in settings["persons"])
    period = {"startDate": "2026-11-09", "endDate": "2026-11-10"}
    preview = api_client.post(PREVIEW, json={**period, "seed": 2}, headers=unique_user.token).json()
    locked = {str(b["index"]): {str(s["slotIndex"]): s["recipe"]["id"] for s in b["slots"]} for b in preview["batches"]}
    assert api_client.post(SAVE, json={**period, "locked": locked}, headers=unique_user.token).status_code == 200

    payload = {"personId": ania, "date": "2026-11-10"}
    result = api_client.post(f"{BASE}/diary/from-plan", json=payload, headers=unique_user.token).json()
    assert result == {"created": 3, "skipped": 0}
    again = api_client.post(f"{BASE}/diary/from-plan", json=payload, headers=unique_user.token).json()
    assert again == {"created": 0, "skipped": 3}

    day = api_client.get(
        f"{BASE}/diary", params={"person_id": ania, "date": "2026-11-10"}, headers=unique_user.token
    ).json()
    planned = {s["slotIndex"]: s for s in preview["batches"][0]["slots"]}
    portions = sorted(next(p["portions"] for p in s["portions"] if p["personId"] == ania) for s in planned.values())
    assert sorted(e["amount"] for e in day["entries"]) == portions
    assert {e["mealType"] for e in day["entries"]} == {"breakfast", "lunch", "dinner"}
    assert abs(day["totals"]["kcal"] - 1800) / 1800 < 0.05

    # Bartek's diary is separate
    bartek_day = api_client.get(
        f"{BASE}/diary", params={"person_id": bartek, "date": "2026-11-10"}, headers=unique_user.token
    )
    assert bartek_day.json()["entries"] == []
