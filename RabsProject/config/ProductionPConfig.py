
UNIQUE_PART_NAMES = [
    "ALTROZ BRACKET-D",
    "ALTROZ BRACKET-E",
    "ALTROZ PES COVER A",
    "ALTROZ PES COVER B",
    "ALTROZ SHADE A MG",
    "ALTROZ INNER LENS A",
    "ALTROZ BACK COVER A",
    "ALTROZ BACK COVER B"
]


# Define alternate groups by machine
ALTERNATE_PART_GROUPS = {
    "120T": [["ALTROZ BRACKET-D", "ALTROZ BRACKET-E"]],
    "250T": [["ALTROZ PES COVER A", "ALTROZ PES COVER B"]],
    "470T": [["ALTROZ INNER LENS A", "ALTROZ SHADE A MG"]],
    "120T": [["ALTROZ BACK COVER A", "ALTROZ BACK COVER B"]],
}



DEFAULT_MONTHLY_PRODUCTION_PLAN_ENTRIES = [

    {
        "part_description": "ALTROZ BRACKET-D",
        "machine": "120T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
      
    },


    {
        "part_description": "ALTROZ BRACKET-E",
        "machine": "120T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
        
    },


     {
        "part_description": "ALTROZ PES COVER A",
        "machine": "250T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
      
    },


    {
        "part_description": "ALTROZ PES COVER B",
        "machine": "250T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
      
    },


    {
        "part_description": "ALTROZ INNER LENS A",
        "machine": "470T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
    },


    {
        "part_description": "ALTROZ SHADE A MG",
        "machine": "470T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
      
    },

    {
        "part_description": "ALTROZ BACK COVER A",
        "machine": "150T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
      
    },

    {
        "part_description": "ALTROZ BACK COVER B",
        "machine": "150T",
        "plan": "",
        "actual_RH": "",
        "actual_LH": "",
        "resp_person": "",
    }
]



PART_CYCLE_TIME_MAP = {
    "ALTROZ BRACKET-D": 32,
    "ALTROZ BRACKET-E": 32,
    "ALTROZ PES COVER A": 50,
    "ALTROZ PES COVER B": 51,
    "ALTROZ SHADE A MG": 49,
    "ALTROZ INNER LENS A": 52,
    "ALTROZ BACK COVER A": 32,
    "ALTROZ BACK COVER B": 32
}

