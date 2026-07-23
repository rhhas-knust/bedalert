"""
Mock data store for the BedAlert demo API.
All patient-facing data is anonymous and aggregated by design:
we only ever store bed COUNTS and AGGREGATE demographic buckets
(age group + sex), never individual patient records.
"""

SURGE_THRESHOLD = 0.85  # occupancy fraction that triggers a surge alert

def _dept(total, available):
    return {"total": total, "available": available}

def _doctors(*entries):
    """entries: (name, specialty, on_call: bool)"""
    return [{"name": n, "specialty": s, "on_call": oc} for n, s, oc in entries]

HOSPITALS = {
    "h1": {
        "id": "h1",
        "name": "St. Mary's General",
        "city": "London",
        "country": "UK",
        "lat": 51.5194,
        "lng": -0.1720,
        "departments": {
            "ER": _dept(20, 4),
            "ICU": _dept(10, 2),
            "general": _dept(60, 18),
        },
        "demographics": {
            "age_groups": {"0-17": 6, "18-39": 22, "40-64": 31, "65+": 19},
            "sex": {"female": 40, "male": 36, "other_unspecified": 2},
        },
        "doctors": _doctors(
            ("Dr. A. Bennett", "Emergency Medicine", True),
            ("Dr. R. Osei", "General Practice", True),
            ("Dr. L. Fenwick", "Cardiology", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h2": {
        "id": "h2",
        "name": "Riverside Medical Center",
        "city": "London",
        "country": "UK",
        "lat": 51.4980,
        "lng": -0.1440,
        "departments": {
            "ER": _dept(15, 1),
            "ICU": _dept(8, 0),
            "general": _dept(40, 5),
        },
        "demographics": {
            "age_groups": {"0-17": 3, "18-39": 15, "40-64": 20, "65+": 17},
            "sex": {"female": 28, "male": 26, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. K. Nwosu", "Emergency Medicine", True),
            ("Dr. S. Patel", "General Practice", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h3": {
        "id": "h3",
        "name": "Northgate District Hospital",
        "city": "Manchester",
        "country": "UK",
        "lat": 53.4808,
        "lng": -2.2426,
        "departments": {
            "ER": _dept(18, 9),
            "ICU": _dept(6, 3),
            "general": _dept(50, 30),
        },
        "demographics": {
            "age_groups": {"0-17": 8, "18-39": 18, "40-64": 22, "65+": 12},
            "sex": {"female": 32, "male": 27, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. M. Yeboah", "Emergency Medicine", True),
            ("Dr. H. Clarke", "Paediatrics", True),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h4": {
        "id": "h4",
        "name": "Nairobi County Referral Hospital",
        "city": "Nairobi",
        "country": "Kenya",
        "lat": -1.2921,
        "lng": 36.8219,
        "departments": {
            "ER": _dept(25, 3),
            "ICU": _dept(5, 1),
            "general": _dept(80, 22),
        },
        "demographics": {
            "age_groups": {"0-17": 20, "18-39": 40, "40-64": 25, "65+": 10},
            "sex": {"female": 52, "male": 42, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. W. Kamau", "Emergency Medicine", True),
            ("Dr. A. Njeri", "Obstetrics", True),
            ("Dr. B. Otieno", "General Practice", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h5": {
        "id": "h5",
        "name": "Lakeview Community Hospital",
        "city": "Kisumu",
        "country": "Kenya",
        "lat": -0.0917,
        "lng": 34.7680,
        "departments": {
            "ER": _dept(10, 6),
            "ICU": _dept(3, 2),
            "general": _dept(30, 19),
        },
        "demographics": {
            "age_groups": {"0-17": 9, "18-39": 14, "40-64": 8, "65+": 4},
            "sex": {"female": 18, "male": 16, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. F. Achieng", "Emergency Medicine", True),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h6": {
        "id": "h6",
        "name": "Austin Metro Health",
        "city": "Austin",
        "country": "USA",
        "lat": 30.2672,
        "lng": -97.7431,
        "departments": {
            "ER": _dept(22, 2),
            "ICU": _dept(12, 1),
            "general": _dept(70, 9),
        },
        "demographics": {
            "age_groups": {"0-17": 5, "18-39": 20, "40-64": 25, "65+": 20},
            "sex": {"female": 36, "male": 33, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. J. Whitfield", "Emergency Medicine", True),
            ("Dr. C. Alvarez", "Cardiology", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h7": {
        "id": "h7",
        "name": "Korle-Bu Teaching Hospital",
        "city": "Accra",
        "country": "Ghana",
        "lat": 5.5362,
        "lng": -0.2266,
        "departments": {
            "ER": _dept(30, 7),
            "ICU": _dept(10, 2),
            "general": _dept(90, 26),
        },
        "demographics": {
            "age_groups": {"0-17": 24, "18-39": 46, "40-64": 28, "65+": 14},
            "sex": {"female": 58, "male": 52, "other_unspecified": 2},
        },
        "doctors": _doctors(
            ("Dr. K. Mensah", "Emergency Medicine", True),
            ("Dr. A. Boateng", "Obstetrics", True),
            ("Dr. E. Sarpong", "General Practice", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h8": {
        "id": "h8",
        "name": "Komfo Anokye Teaching Hospital",
        "city": "Kumasi",
        "country": "Ghana",
        "lat": 6.6885,
        "lng": -1.6244,
        "departments": {
            "ER": _dept(24, 5),
            "ICU": _dept(8, 1),
            "general": _dept(65, 15),
        },
        "demographics": {
            "age_groups": {"0-17": 18, "18-39": 30, "40-64": 20, "65+": 9},
            "sex": {"female": 40, "male": 36, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. Y. Owusu", "Emergency Medicine", True),
            ("Dr. P. Asante", "Paediatrics", False),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
    "h9": {
        "id": "h9",
        "name": "Tamale Teaching Hospital",
        "city": "Tamale",
        "country": "Ghana",
        "lat": 9.4008,
        "lng": -0.8393,
        "departments": {
            "ER": _dept(16, 8),
            "ICU": _dept(4, 2),
            "general": _dept(40, 20),
        },
        "demographics": {
            "age_groups": {"0-17": 15, "18-39": 20, "40-64": 12, "65+": 5},
            "sex": {"female": 27, "male": 24, "other_unspecified": 1},
        },
        "doctors": _doctors(
            ("Dr. I. Alhassan", "Emergency Medicine", True),
        ),
        "notifications": [],
        "last_updated": "2026-07-09T08:00:00Z",
    },
}

ALERTS = []
EMERGENCY_LOG = []  # shared feed: emergencies raised from ANY tier (public, SMS, dispatcher)
