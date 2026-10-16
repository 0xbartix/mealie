import pytest

from mealie.services.diet.freezer import Change, Macros, MoldGroup, compute_batch
from mealie.services.diet.off_client import parse_product

GULASZ = Macros(580, 40, 20, 60)  # per serving
RICE = Macros(130, 2.7, 0.3, 28)  # per 100 g
GROATS = Macros(92, 3.4, 0.6, 19.9)
CHEESE = Macros(350, 25, 27, 1)


def test_base_is_servings_times_recipe():
    result = compute_batch(GULASZ, 6, [], [MoldGroup(500, 6)])
    assert result.total == Macros(3480, 240, 120, 360)
    assert result.per_mold == [Macros(580, 40, 20, 60)]


def test_add_remove_and_swap_change_the_total():
    changes = [
        Change("add", CHEESE, 50),  # +175 kcal
        Change("remove", RICE, 100),  # -130 kcal
        Change("swap", GROATS, 200, replaced=RICE, replaced_grams=200),  # +184 - 260 = -76 kcal
    ]
    result = compute_batch(GULASZ, 4, changes, [MoldGroup(250, 8)])
    assert [round(d.kcal, 1) for d in result.deltas] == [175, -130, -76]
    assert round(result.total.kcal, 1) == 4 * 580 + 175 - 130 - 76
    assert round(result.total.protein, 2) == round(160 + 12.5 - 2.7 + 6.8 - 5.4, 2)


def test_molds_of_different_sizes_split_by_capacity():
    result = compute_batch(GULASZ, 3, [], [MoldGroup(500, 2), MoldGroup(250, 2)])
    big, small = result.per_mold
    assert big.kcal == pytest.approx(2 * small.kcal)
    assert 2 * big.kcal + 2 * small.kcal == pytest.approx(3 * 580)


def test_override_replaces_the_total_and_negatives_are_clamped():
    result = compute_batch(GULASZ, 1, [], [MoldGroup(500, 2)], override=Macros(1000, 50, 40, 100))
    assert result.total == Macros(1000, 50, 40, 100)
    assert result.per_mold == [Macros(500, 25, 20, 50)]

    removed_too_much = compute_batch(GULASZ, 1, [Change("remove", CHEESE, 1000)], [MoldGroup(100, 1)])
    assert removed_too_much.total.kcal == 0 and removed_too_much.total.fat == 0


def test_parse_off_product():
    product = parse_product(
        {
            "code": "5900512320359",
            "product_name": "Mleko WYPASIONE 3,2%",
            "product_name_pl": "Mleko 3,2%",
            "brands": "Mlekovita, Inna",
            "quantity": "1l",
            "serving_size": "1 szklanka (250 ml)",
            "serving_quantity": "250",
            "nutriments": {"energy-kcal_100g": 60, "proteins_100g": 3.2, "fat_100g": 3.2, "carbohydrates_100g": 4.7},
        }
    )
    assert product is not None
    assert (product.name, product.brand, product.unit) == ("Mleko 3,2%", "Mlekovita", "ml")
    assert (product.kcal, product.protein, product.fat, product.carbs) == (60, 3.2, 3.2, 4.7)
    assert (product.portion_name, product.portion_grams) == ("1 szklanka (250 ml)", 250)


def test_parse_off_product_kj_fallback_and_rejects():
    from_kj = parse_product(
        {"code": "1", "product_name": "X", "brands": ["", "Marka"], "nutriments": {"energy_100g": 418.4}}
    )
    assert from_kj is not None and from_kj.kcal == 100 and from_kj.brand == "Marka" and from_kj.unit == "g"
    assert parse_product({"code": "1", "product_name": "Bez kalorii", "nutriments": {}}) is None
    assert parse_product({"code": "1", "nutriments": {"energy-kcal_100g": 10}}) is None
