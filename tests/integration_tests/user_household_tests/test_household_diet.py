import io
import zipfile
from datetime import date

from fastapi.testclient import TestClient

from tests.utils import api_routes
from tests.utils.fixture_schemas import TestUser

SETTINGS = "/api/households/diet/settings"
PREVIEW = "/api/households/diet/plan/preview"
SAVE = "/api/households/diet/plan/save"
IMPORT = "/api/households/diet/import"

MON = date(2026, 10, 19)


def recipe_md(name: str, meal: str, kcal: float, protein: float, fat: float, carbs: float, servings: int = 4) -> str:
    return f"""---
nazwa: {name}
porcje: {servings}
posilek: [{meal}]
kcal: {kcal}
bialko: {protein}
tluszcz: {fat}
weglowodany: {carbs}
czas: 20
tagi: [test-diety]
---
Opis {name}.

## Składniki
- 100 g ryż biały
- 2 łyżki oliwa, extra virgin
- 1 szt cebula

## Przygotowanie
1. Ugotuj ryż.
2. Podsmaż cebulę.
"""


def balanced(name: str, meal: str, kcal: float) -> str:
    return recipe_md(name, meal, kcal, round(kcal * 0.25 / 4), round(kcal * 0.30 / 9), round(kcal * 0.45 / 4))


def upload(api_client: TestClient, user: TestUser, files: dict[str, bytes]):
    payload = [("files", (name, content, "application/octet-stream")) for name, content in files.items()]
    return api_client.post(IMPORT, files=payload, headers=user.token)


def seed_recipes(api_client: TestClient, user: TestUser) -> None:
    files = {}
    for meal, base in (("sniadanie", 450), ("obiad", 650), ("kolacja", 500)):
        for i in range(3):
            files[f"{meal}-{i}.md"] = balanced(f"{meal} {i} {user.user_id}", meal, base + 40 * i).encode()
    response = upload(api_client, user, files)
    assert response.status_code == 200, response.text
    assert all(r["status"] == "created" for r in response.json()["results"])


def configure(api_client: TestClient, user: TestUser) -> dict:
    payload = {
        "persons": [
            {"name": "Bartek", "kcal": 2500, "protein": 156, "fat": 83, "carbs": 281},
            {"name": "Ania", "kcal": 1800, "protein": 112, "fat": 60, "carbs": 202},
        ],
        "cookingDays": [6, 2],
        "mealSlots": [
            {"mealType": "breakfast", "share": 30},
            {"mealType": "lunch", "share": 40},
            {"mealType": "dinner", "share": 30},
        ],
    }
    response = api_client.put(SETTINGS, json=payload, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


def test_settings_defaults_and_validation(api_client: TestClient, unique_user: TestUser):
    response = api_client.get(SETTINGS, headers=unique_user.token)
    assert response.status_code == 200
    data = response.json()
    assert data["persons"] == []
    assert data["cookingDays"] == [6]
    assert [s["share"] for s in data["mealSlots"]] == [30, 40, 30]

    saved = configure(api_client, unique_user)
    assert saved["cookingDays"] == [2, 6]
    assert [p["name"] for p in saved["persons"]] == ["Bartek", "Ania"]
    assert all(p["id"] for p in saved["persons"])
    assert api_client.get(SETTINGS, headers=unique_user.token).json()["persons"] == saved["persons"]

    bad = {"persons": [], "cookingDays": [6], "mealSlots": [{"mealType": "lunch", "share": 60}]}
    assert api_client.put(SETTINGS, json=bad, headers=unique_user.token).status_code == 422
    bad = {"persons": [], "cookingDays": [], "mealSlots": [{"mealType": "lunch", "share": 100}]}
    assert api_client.put(SETTINGS, json=bad, headers=unique_user.token).status_code == 422


def test_import_creates_updates_and_reports_errors(api_client: TestClient, unique_user: TestUser):
    name = f"Gulasz {unique_user.user_id}"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("przepisy/kolacja.md", balanced(f"Sałatka {unique_user.user_id}", "kolacja", 400))
        zf.writestr("__MACOSX/._kolacja.md", "junk")

    response = upload(
        api_client,
        unique_user,
        {
            "gulasz.md": recipe_md(name, "obiad", 600, 40, 20, 60).encode(),
            "zly.md": b"---\nnazwa: Zly\n---\n",
            "obrazek.png": b"\x89PNG",
            "paczka.zip": archive.getvalue(),
        },
    )
    assert response.status_code == 200, response.text
    results = {r["fileName"]: r for r in response.json()["results"]}
    assert results["gulasz.md"]["status"] == "created"
    assert results["przepisy/kolacja.md"]["status"] == "created"
    assert results["zly.md"]["status"] == "error"
    assert "brak pola „porcje”" in results["zly.md"]["errors"]
    assert results["obrazek.png"]["status"] == "error"
    assert "__MACOSX/._kolacja.md" not in results

    slug = results["gulasz.md"]["recipeSlug"]
    recipe = api_client.get(api_routes.recipes_slug(slug), headers=unique_user.token).json()
    assert recipe["recipeServings"] == 4
    assert recipe["nutrition"]["calories"] == "600"
    assert recipe["nutrition"]["proteinContent"] == "40"
    assert recipe["settings"]["showNutrition"] is True
    assert [c["name"] for c in recipe["recipeCategory"]] == ["Obiad"]
    assert [t["name"] for t in recipe["tags"]] == ["test-diety"]
    assert recipe["totalTimeSeconds"] == 1200
    assert [i["food"]["name"] for i in recipe["recipeIngredient"]] == ["ryż biały", "oliwa", "cebula"]
    assert [i["unit"]["name"] for i in recipe["recipeIngredient"]] == ["g", "łyżka", "szt"]
    assert recipe["recipeIngredient"][1]["note"] == "extra virgin"
    assert [s["text"] for s in recipe["recipeInstructions"]] == ["Ugotuj ryż.", "Podsmaż cebulę."]

    # re-importing the same name updates the recipe instead of duplicating it
    response = upload(
        api_client, unique_user, {"gulasz.md": recipe_md(name, "obiad, kolacja", 700, 45, 25, 70).encode()}
    )
    result = response.json()["results"][0]
    assert result["status"] == "updated"
    assert result["recipeSlug"] == slug
    recipe = api_client.get(api_routes.recipes_slug(slug), headers=unique_user.token).json()
    assert recipe["nutrition"]["calories"] == "700"
    assert sorted(c["name"] for c in recipe["recipeCategory"]) == ["Kolacja", "Obiad"]
    assert len(recipe["recipeIngredient"]) == 3

    # foods and units are reused, not duplicated
    foods = api_client.get(api_routes.foods, params={"perPage": -1}, headers=unique_user.token).json()["items"]
    assert [f["name"] for f in foods].count("ryż biały") == 1


def test_preview_swap_and_save(api_client: TestClient, unique_user: TestUser):
    seed_recipes(api_client, unique_user)
    configure(api_client, unique_user)
    period = {"startDate": MON.isoformat(), "endDate": "2026-10-25"}

    response = api_client.post(PREVIEW, json={**period, "seed": 5}, headers=unique_user.token)
    assert response.status_code == 200, response.text
    preview = response.json()
    # Mon-Tue (start of period), Wed-Sat, Sun
    assert [(b["startDate"], b["days"]) for b in preview["batches"]] == [
        ("2026-10-19", 2),
        ("2026-10-21", 4),
        ("2026-10-25", 1),
    ]
    first = preview["batches"][0]
    assert [s["mealType"] for s in first["slots"]] == ["breakfast", "lunch", "dinner"]
    for total, target in zip(first["totals"], (2500, 1800), strict=True):
        assert abs(total["kcal"] - target) / target < 0.05

    # swap the lunch of batch 0, keeping the other slots
    locked = {str(b["index"]): {str(s["slotIndex"]): s["recipe"]["id"] for s in b["slots"]} for b in preview["batches"]}
    lunch_id = locked["0"].pop("1")
    swap = {**period, "seed": preview["seed"], "locked": locked, "excluded": {"0": {"1": [lunch_id]}}}
    swapped = api_client.post(PREVIEW, json=swap, headers=unique_user.token).json()
    assert swapped["batches"][0]["slots"][1]["recipe"]["id"] != lunch_id
    assert swapped["batches"][0]["slots"][0]["recipe"]["id"] == locked["0"]["0"]

    # a manual entry inside the period must survive saving and re-saving
    manual = api_client.post(
        api_routes.households_mealplans,
        json={"date": "2026-10-20", "entryType": "snack", "title": "Jabłko"},
        headers=unique_user.token,
    )
    assert manual.status_code == 201

    final_locked = {
        str(b["index"]): {str(s["slotIndex"]): s["recipe"]["id"] for s in b["slots"]} for b in swapped["batches"]
    }
    save = {**period, "locked": final_locked}
    response = api_client.post(SAVE, json=save, headers=unique_user.token)
    assert response.status_code == 200, response.text
    assert response.json() == {"created": 21, "removed": 0}

    entries = api_client.get(
        api_routes.households_mealplans,
        params={"start_date": "2026-10-19", "end_date": "2026-10-25", "perPage": -1},
        headers=unique_user.token,
    ).json()["items"]
    assert len(entries) == 22
    assert any(e["title"] == "Jabłko" for e in entries)

    batch = swapped["batches"][1]  # Wed..Sat
    lunch = batch["slots"][1]
    wednesday_lunch = next(e for e in entries if e["date"] == "2026-10-21" and e["entryType"] == "lunch")
    assert wednesday_lunch["recipeId"] == lunch["recipe"]["id"]
    assert wednesday_lunch["recipeScale"] == lunch["portionsPerDay"] / lunch["recipe"]["servings"]
    assert wednesday_lunch["text"].startswith("Ugotuj ")
    assert "na 4 dni" in wednesday_lunch["text"]
    assert "Bartek:" in wednesday_lunch["text"] and "Ania:" in wednesday_lunch["text"]
    thursday_lunch = next(e for e in entries if e["date"] == "2026-10-22" and e["entryType"] == "lunch")
    assert not thursday_lunch["text"].startswith("Ugotuj")

    # saving again replaces only the planner's own entries
    response = api_client.post(SAVE, json=save, headers=unique_user.token)
    assert response.json() == {"created": 21, "removed": 21}
    entries = api_client.get(
        api_routes.households_mealplans,
        params={"start_date": "2026-10-19", "end_date": "2026-10-25", "perPage": -1},
        headers=unique_user.token,
    ).json()["items"]
    assert len(entries) == 22


def test_preview_requires_persons(api_client: TestClient, unique_user: TestUser):
    # unique_user is shared within the module, so clear the persons set up by other tests
    settings = api_client.get(SETTINGS, headers=unique_user.token).json()
    settings["persons"] = [{**p, "active": False} for p in settings["persons"]]
    assert api_client.put(SETTINGS, json=settings, headers=unique_user.token).status_code == 200

    response = api_client.post(
        PREVIEW, json={"startDate": "2026-10-19", "endDate": "2026-10-20"}, headers=unique_user.token
    )
    assert response.status_code == 400
    assert response.json()["detail"]["message"] == "no-persons"


def test_preview_rejects_bad_period(api_client: TestClient, unique_user: TestUser):
    configure(api_client, unique_user)
    response = api_client.post(
        PREVIEW, json={"startDate": "2026-10-19", "endDate": "2026-10-18"}, headers=unique_user.token
    )
    assert response.status_code == 422
    response = api_client.post(
        PREVIEW, json={"startDate": "2026-10-01", "endDate": "2026-12-31"}, headers=unique_user.token
    )
    assert response.status_code == 422
