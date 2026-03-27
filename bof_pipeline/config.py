"""Domain dictionaries for BOF 1901-1902 text interpretation."""

from __future__ import annotations


ACTION_STATUS_PATTERNS = {
    "Approved": [
        r"\bapproved\b",
        r"\badopted\b",
        r"\bauthori[sz]ed\b",
        r"\ballotment made\b",
        r"\ballotted\b",
        r"\bgranted\b",
        r"\baccepted\b",
        r"\bcontract awarded\b",
        r"\bordered\b",
        r"\brecommended for adoption\b",
        r"\bappropriation made\b",
    ],
    "Rejected": [
        r"\brejected\b",
        r"\bdisapproved\b",
        r"\bdeclined\b",
        r"\bnot approved\b",
        r"\bdenied\b",
        r"\bno action\b",
        r"\bnot adopted\b",
        r"\bwithdrawn\b",
        r"\bunfavorable\b",
    ],
    "Investigating": [
        r"\bfiled\b",
        r"\baction deferred\b",
        r"\bdeferred\b",
        r"\breferred\b",
        r"\bfor report\b",
        r"\bunder consideration\b",
        r"\bpending\b",
        r"\bcontinued\b",
        r"\bpostponed\b",
        r"\bfor trial\b",
        r"\bfor test\b",
        r"\bno final action\b",
    ],
}


TECHNOLOGY_CLUSTER_PATTERNS = {
    "Artillery": [
        r"\bgun\b",
        r"\bcannon\b",
        r"\bhowitzer\b",
        r"\bfield piece\b",
        r"\bvickers\b",
        r"\bordnance\b",
        r"\bcarriage\b",
    ],
    "Explosives": [
        r"\bshell\b",
        r"\bpowder\b",
        r"\bexplosive\b",
        r"\bdetonator\b",
        r"\bfuse\b",
        r"\btorpedo\b",
        r"\bmine\b",
        r"\bisham\b",
    ],
    "Small Arms": [
        r"\brifle\b",
        r"\bpistol\b",
        r"\bmusket\b",
        r"\bcarbine\b",
        r"\bsmall arm\b",
        r"\bmachine gun\b",
    ],
    "Armor and Protection": [
        r"\barmor\b",
        r"\barmour\b",
        r"\bshield\b",
        r"\bhelmet\b",
        r"\bprotective\b",
        r"\bfortification plate\b",
    ],
    "Fortification and Engineering": [
        r"\bfort\b",
        r"\bfortification\b",
        r"\bbattery\b",
        r"\bemplacement\b",
        r"\brange finder\b",
        r"\bsearchlight\b",
        r"\bengineering\b",
        r"\bsiege\b",
    ],
    "Communications and Observation": [
        r"\btelegraph\b",
        r"\btelephone\b",
        r"\bsignal\b",
        r"\bobservation\b",
        r"\boptical\b",
        r"\bwireless\b",
    ],
    "Logistics and Support": [
        r"\bwagon\b",
        r"\btransport\b",
        r"\bsupply\b",
        r"\bquartermaster\b",
        r"\bpack\b",
        r"\bmedical\b",
    ],
}


GOVERNMENT_PROPOSER_PATTERNS = [
    r"\bwar department\b",
    r"\bordnance department\b",
    r"\bchief of ordnance\b",
    r"\bu\.?s\.? army\b",
    r"\bsecretary of war\b",
    r"\bboard of ordnance\b",
    r"\bdepartment\b",
    r"\barsenal\b",
    r"\bcommanding officer\b",
]


COLUMN_ALIASES = {
    "subject": ["subject", "topic", "title", "matter"],
    "action": ["action", "decision", "board action", "disposition", "status text"],
    "reasoning": [
        "recommendation reasoning",
        "reasoning",
        "recommendation",
        "remarks",
        "notes",
    ],
    "proposer": ["proposer", "submitted by", "originator", "applicant", "proposed by"],
    "year": [
        "year",
        "date",
        "fiscal year",
        "calendar year",
        "bof annual report #",
        "annual report",
        "report #",
    ],
}
