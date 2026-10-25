"""Tests for business input rules (no database needed)."""
import pytest
from pydantic import ValidationError

from app.schemas.business import BusinessCreate, BusinessUpdate
from app.services.businesses import MAX_SLUG_LENGTH, slugify


@pytest.mark.parametrize("name, expected", [
    ("Lumen Fitness", "lumen-fitness"),
    ("Lumen Fitness & Yoga!", "lumen-fitness-yoga"),
    ("  Café Élan  ", "cafe-elan"),
    ("Studio 54", "studio-54"),
    ("!!!", "business"),
])
def test_slugify_makes_clean_booking_links(name, expected):
    assert slugify(name) == expected


def test_slug_is_limited_in_length():
    assert len(slugify("a very long business name " * 10)) <= MAX_SLUG_LENGTH


def test_valid_business_is_accepted():
    data = BusinessCreate(name="Lumen Fitness", category="personal_trainer", timezone="Asia/Kolkata")
    assert data.currency == "USD"


@pytest.mark.parametrize("fields", [
    {"name": "X", "category": "salon"},                                   # name too short
    {"name": "Lumen", "category": "spaceship_repair"},                    # unknown category
    {"name": "Lumen", "category": "salon", "timezone": "Mars/Base"},      # unknown time zone
    {"name": "Lumen", "category": "salon", "currency": "usd"},            # currency must be uppercase code
    {"name": "Lumen", "category": "salon", "latitude": 120},              # impossible coordinate
    {"name": "Lumen", "category": "salon", "status": "live"},             # status can't be set by the owner
    {"name": "Lumen", "category": "salon", "paypal_merchant_id": "X1"},   # PayPal fields can't be set either
])
def test_invalid_business_input_is_rejected(fields):
    with pytest.raises(ValidationError):
        BusinessCreate(**fields)


def test_update_only_includes_sent_fields():
    update = BusinessUpdate(privacy_mode=True)
    assert update.model_dump(exclude_unset=True) == {"privacy_mode": True}


def test_update_cannot_blank_required_fields():
    with pytest.raises(ValidationError):
        BusinessUpdate(name=None)


@pytest.mark.parametrize("vocabulary", [{"price": "cost"}, {"booking": ""}, {"booking": "x" * 31}])
def test_bad_vocabulary_is_rejected(vocabulary):
    with pytest.raises(ValidationError):
        BusinessUpdate(vocabulary=vocabulary)