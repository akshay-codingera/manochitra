"""Canonical assignment concepts and their source text.

The wording below follows the five concepts in the Udhi assignment (page 3).
Do not silently paraphrase this source text before sending it to the model.
"""

CONCEPTS = [
    {
        "id": "pythagoras",
        "number": 1,
        "name": "Pythagoras' theorem",
        "subject": "Maths",
        "source_text": (
            "In a right-angled triangle, the longest side is called the hypotenuse. "
            "The square of the hypotenuse is equal to the sum of the squares of the "
            "other two sides: a² + b² = c²."
        ),
        "required_terms": ["hypotenuse", "right angle", "a²", "b²", "c²"],
        "minimum_term_fraction": 0.8,
    },
    {
        "id": "circle",
        "number": 2,
        "name": "Parts of a circle",
        "subject": "Maths",
        "source_text": (
            "A circle has a centre. The radius is the distance from the centre to the edge. "
            "The diameter goes across the circle through the centre and is twice the "
            "radius. The circumference is the distance around the circle."
        ),
        "required_terms": ["centre", "radius", "diameter", "circumference"],
        "minimum_term_fraction": 1.0,
    },
    {
        "id": "series-circuit",
        "number": 3,
        "name": "Series circuit",
        "subject": "Physics",
        "source_text": (
            "In a series circuit there is only one loop. The current is the same "
            "everywhere in the loop. The voltage of the cell is shared between the components."
        ),
        "required_terms": ["one loop", "current", "voltage", "cell"],
        "minimum_term_fraction": 0.75,
    },
    {
        "id": "photosynthesis",
        "number": 4,
        "name": "Photosynthesis",
        "subject": "Biology",
        "source_text": (
            "Plants take in carbon dioxide and water. They use light energy, absorbed by "
            "chlorophyll, to make glucose and oxygen."
        ),
        "required_terms": ["carbon dioxide", "water", "light", "chlorophyll", "glucose", "oxygen"],
        "minimum_term_fraction": 0.83,
    },
    {
        "id": "states-of-matter",
        "number": 5,
        "name": "States of matter",
        "subject": "Chemistry",
        "source_text": (
            "In a solid the particles are close together and vibrate in place. In a liquid "
            "they are close but move past each other. In a gas they are far apart and move fast."
        ),
        "required_terms": ["solid", "liquid", "gas", "particles", "vibrate"],
        "minimum_term_fraction": 0.8,
    },
]

CONCEPT_BY_ID = {concept["id"]: concept for concept in CONCEPTS}
