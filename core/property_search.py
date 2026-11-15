"""Plain database search for properties — no AI involved.

The facts-only guard needs to know which properties are real, so the AI
can be told about them and never has to invent one. This file is the
only thing allowed to decide "which properties match a request" — the AI
does not search anything, it only describes what this file found.
"""
from core.models import Property


def find_matching_properties(city=None, bedrooms=None, max_price=None):
    """Return the real properties matching a customer's request.

    All three filters are optional — pass only the ones the customer
    gave. `city` matches case-insensitively. `bedrooms` is an exact
    match. `max_price` excludes anything above that price.
    """
    queryset = Property.objects.all()

    if city:
        queryset = queryset.filter(city__iexact=city)
    if bedrooms is not None:
        queryset = queryset.filter(bedrooms=bedrooms)
    if max_price is not None:
        queryset = queryset.filter(price__lte=max_price)

    return list(queryset)


def properties_as_facts(properties):
    """Turn real Property rows into a plain-text block to hand to the AI,
    so it can only describe real listings and never has to invent one."""
    if not properties:
        return "No matching properties were found in our database."

    lines = [
        f"- {prop.title}: {prop.bedrooms} bedroom {prop.type} in "
        f"{prop.area}, {prop.city}. Price: {prop.price} {prop.currency}. "
        f"Status: {prop.status}."
        for prop in properties
    ]
    return "\n".join(lines)
