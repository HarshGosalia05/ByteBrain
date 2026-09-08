"""MD-06 Career Intelligence — pure deterministic rules.

No ML, no GenAI, no DB access. Thresholds and weights live in
``app.core.config`` following the Threshold Engine convention.

Career Readiness score
----------------------
The score is the weighted average of up to six 0-100 components:

    academic     mean of the latest-attempt completed subject percentages.
    consistency  100 - (std-dev of completed-semester SGPA * scale); needs at
                 least two completed semesters.
    alignment    mean % of completed subjects that are domain-relevant for the
                 student's preferred domain (see DOMAIN_SUBJECT_KEYWORDS).
    attendance   current-semester aggregate attendance % (falls back to the
                 latest completed semester's stored attendance, then to the
                 stored overall attendance).
    internship   career_preferences.internship_completed mapped to 100 ('Yes')
                 or 0 ('No').
    readiness    career_preferences.placement_readiness_level mapped to a
                 score (Low 25 / Medium 50 / High 75 / Excellent 100).

Weights are configurable; the sum is renormalized over the *available*
components. If fewer than ``CAREER_READINESS_AVAILABLE_COMPONENT_MIN``
components are available the score is not shown (insufficient data). Bands:

    >= 80 Strong | >= 60 Good | >= 40 Developing | below Needs Attention

Domain alignment
----------------
A completed subject counts as domain-relevant when its name matches one of the
configured keywords for the student's preferred domain. Alignment = the share
of completed subjects that are domain-relevant (0-100). NULL is never treated
as zero and a pending (unpublished) result is never fabricated.
"""

import statistics
from typing import Any, Dict, List, Optional

from app.core.config import settings

# Deterministic, configuration-based mapping of career domains to the subject
# keywords that make a subject domain-relevant. Matches are case-insensitive
# substrings against the canonical subject name.
DOMAIN_SUBJECT_KEYWORDS: Dict[str, List[str]] = {
    "Data Science": [
        "data", "statistics", "analytics", "machine learning",
        "artificial intelligence", "python", "probability", "database",
    ],
    "Cyber Security": [
        "security", "cryptography", "computer networks", "network", "operating systems",
    ],
    "Backend Development": [
        "java", "python", "database", "operating systems", "object oriented",
        "programming", "scripting", "compiler", "software", "linux",
    ],
    "Mobile Development": [
        "mobile", "android", "java", "programming", "object oriented",
    ],
    "UI / UX": [
        "human computer interaction", "design", "computer programming",
        "computer applications", "software engineering",
    ],
    "Full Stack Development": [
        "java", "python", "database", "web", "software", "scripting",
        "programming", "operating systems", "object oriented",
    ],
    "AI / ML": [
        "artificial intelligence", "machine learning", "deep learning",
        "natural language", "python", "statistics", "probability",
        "data", "recommender", "image", "computer vision",
    ],
    "Cloud Computing": [
        "cloud", "operating systems", "computer networks", "virtualization",
    ],
    "DevOps": [
        "linux", "scripting", "operating systems", "computer networks", "cloud",
    ],
    "Software Development": [
        "java", "python", "software", "programming", "database",
        "operating systems", "object oriented", "scripting", "compiler",
    ],
    "Business Analytics": [
        "analytics", "statistics", "business statistics", "computer applications",
        "management information systems", "business mathematics", "research methodology",
    ],
    "Operations": [
        "operations", "supply chain", "production", "project management",
    ],
    "Marketing": [
        "marketing", "consumer behavior", "digital marketing", "retail",
        "services marketing", "business communication",
    ],
    "Digital Marketing": [
        "digital marketing", "marketing", "e-commerce", "consumer behavior",
    ],
    "Banking": [
        "banking", "financial", "income tax", "investment", "business economics",
        "financial accounting", "cost accounting", "business law",
    ],
    "Finance": [
        "financial", "income tax", "investment", "banking", "business economics",
        "financial accounting", "cost accounting",
    ],
    "Human Resources": [
        "human resource", "organizational behavior", "personality development",
        "business communication", "leadership",
    ],
    "Sales": [
        "marketing", "retail", "consumer behavior", "business communication",
    ],
    "Entrepreneurship": [
        "entrepreneurship", "innovation", "strategic management", "project management",
    ],
}

PLACEMENT_READINESS_SCORES: Dict[str, float] = {
    "Low": 25.0,
    "Medium": 50.0,
    "High": 75.0,
    "Excellent": 100.0,
}

# Domain -> career path recommendations (roles, skills, certifications, projects).
# Used by the Recommended Career Path section; every value is domain-specific.
DOMAIN_CAREER_PATHS: Dict[str, Dict[str, Any]] = {
    "Data Science": {
        "roles": [
            "Data Analyst",
            "Data Scientist",
            "Machine Learning Engineer",
            "Business Intelligence Analyst",
            "Analytics Engineer",
        ],
        "skills": [
            "Python",
            "SQL",
            "Statistics",
            "Machine Learning",
            "Data Visualization",
            "Pandas / NumPy",
            "R",
            "Tableau / Power BI",
        ],
        "certifications": [
            "Google Data Analytics Professional Certificate",
            "IBM Data Science Professional Certificate",
            "Microsoft Certified: Data Analyst Associate",
            "AWS Certified Machine Learning – Specialty",
        ],
        "project_suggestions": [
            "Build an end-to-end exploratory data analysis project on a real-world dataset",
            "Create a predictive model and deploy it as a simple web app",
            "Develop an interactive dashboard using Tableau or Power BI",
        ],
    },
    "Cyber Security": {
        "roles": [
            "Cyber Security Analyst",
            "Security Engineer",
            "SOC Analyst",
            "Penetration Tester",
            "Information Security Analyst",
        ],
        "skills": [
            "Computer Networks",
            "Cryptography",
            "Operating Systems",
            "Network Security",
            "Linux",
            "Threat Detection",
            "Firewall Configuration",
            "Vulnerability Assessment",
        ],
        "certifications": [
            "CompTIA Security+",
            "Certified Ethical Hacker (CEH)",
            "CompTIA Network+",
            "Cisco Certified CyberOps Associate",
        ],
        "project_suggestions": [
            "Set up a home lab with firewall rules and monitor network traffic",
            "Complete a Capture The Flag (CTF) challenge on TryHackMe or HackTheBox",
            "Build a simple intrusion detection system using open-source tools",
        ],
    },
    "Backend Development": {
        "roles": [
            "Backend Developer",
            "Java Developer",
            "API Engineer",
            "Software Developer",
            "Systems Programmer",
        ],
        "skills": [
            "Java",
            "Python",
            "SQL / Databases",
            "REST APIs",
            "Operating Systems",
            "Git / Version Control",
            "Object-Oriented Programming",
            "Linux",
        ],
        "certifications": [
            "Oracle Certified Professional: Java SE Developer",
            "AWS Certified Developer – Associate",
            "Microsoft Certified: Azure Developer Associate",
        ],
        "project_suggestions": [
            "Build a RESTful API with authentication and database integration",
            "Develop a microservices application with Docker",
            "Contribute to an open-source backend project on GitHub",
        ],
    },
    "Mobile Development": {
        "roles": [
            "Android Developer",
            "iOS Developer",
            "Mobile App Developer",
            "Cross-Platform Developer",
            "Flutter Developer",
        ],
        "skills": [
            "Java / Kotlin",
            "Swift",
            "Flutter / Dart",
            "React Native",
            "Mobile UI/UX",
            "REST APIs",
            "SQLite / Room",
            "Firebase",
        ],
        "certifications": [
            "Google Associate Android Developer",
            "Meta Android Developer Professional Certificate",
            "Apple Certified iOS Developer",
        ],
        "project_suggestions": [
            "Build and publish a complete mobile app on Play Store or App Store",
            "Develop a cross-platform app using Flutter with backend integration",
            "Create a portfolio app showcasing your academic projects",
        ],
    },
    "UI / UX": {
        "roles": [
            "UI/UX Designer",
            "Product Designer",
            "Interaction Designer",
            "UX Researcher",
            "Visual Designer",
        ],
        "skills": [
            "Figma",
            "Adobe XD",
            "User Research",
            "Wireframing & Prototyping",
            "Human Computer Interaction",
            "Design Systems",
            "HTML / CSS",
            "Usability Testing",
        ],
        "certifications": [
            "Google UX Design Professional Certificate",
            "IBM UX Design Professional Certificate",
            "Interaction Design Foundation courses",
        ],
        "project_suggestions": [
            "Design a complete mobile app UI from wireframes to high-fidelity mockups",
            "Conduct user research and create persona-driven design solutions",
            "Build a personal design portfolio website on Behance or Dribbble",
        ],
    },
    "Full Stack Development": {
        "roles": [
            "Full Stack Developer",
            "Web Developer",
            "Software Engineer",
            "Frontend + Backend Developer",
            "Application Developer",
        ],
        "skills": [
            "JavaScript / TypeScript",
            "React / Next.js",
            "Node.js / Express",
            "SQL / NoSQL Databases",
            "REST APIs",
            "Git / Version Control",
            "HTML / CSS",
            "Docker",
        ],
        "certifications": [
            "Meta Front-End Developer Professional Certificate",
            "AWS Certified Developer – Associate",
            "MongoDB Certified Developer Associate",
        ],
        "project_suggestions": [
            "Build and deploy a full-stack web application with authentication",
            "Develop a real-time chat application using WebSockets",
            "Create a personal portfolio site with a backend CMS",
        ],
    },
    "AI / ML": {
        "roles": [
            "Machine Learning Engineer",
            "AI Researcher",
            "NLP Engineer",
            "Computer Vision Engineer",
            "Applied Scientist",
        ],
        "skills": [
            "Python",
            "Machine Learning / Deep Learning",
            "TensorFlow / PyTorch",
            "Natural Language Processing",
            "Computer Vision",
            "Statistics / Probability",
            "Data Preprocessing",
            "Model Deployment",
        ],
        "certifications": [
            "TensorFlow Developer Certificate",
            "AWS Certified Machine Learning – Specialty",
            "Deep Learning Specialization (Coursera)",
        ],
        "project_suggestions": [
            "Train and deploy an image classification model as a web service",
            "Build a sentiment analysis tool using NLP techniques",
            "Participate in a Kaggle competition and document your approach",
        ],
    },
    "Cloud Computing": {
        "roles": [
            "Cloud Engineer",
            "Cloud Architect",
            "DevOps Engineer",
            "Solutions Architect",
            "Site Reliability Engineer",
        ],
        "skills": [
            "AWS / Azure / GCP",
            "Linux",
            "Networking",
            "Virtualization",
            "Docker / Kubernetes",
            "Infrastructure as Code",
            "Monitoring & Logging",
            "Security",
        ],
        "certifications": [
            "AWS Certified Solutions Architect – Associate",
            "Microsoft Certified: Azure Fundamentals",
            "Google Cloud Professional Cloud Architect",
        ],
        "project_suggestions": [
            "Deploy a multi-tier application on AWS or Azure with auto-scaling",
            "Set up a CI/CD pipeline using GitHub Actions and cloud services",
            "Build a serverless application using AWS Lambda or Azure Functions",
        ],
    },
    "DevOps": {
        "roles": [
            "DevOps Engineer",
            "Site Reliability Engineer",
            "Platform Engineer",
            "Infrastructure Engineer",
            "Release Engineer",
        ],
        "skills": [
            "Linux",
            "Docker / Kubernetes",
            "CI/CD Pipelines",
            "Terraform / Ansible",
            "Cloud Platforms",
            "Monitoring (Prometheus/Grafana)",
            "Scripting (Bash/Python)",
            "Networking",
        ],
        "certifications": [
            "Certified Kubernetes Administrator (CKA)",
            "AWS Certified DevOps Engineer – Professional",
            "Docker Certified Associate",
        ],
        "project_suggestions": [
            "Set up a complete CI/CD pipeline for a web application",
            "Automate infrastructure provisioning using Terraform",
            "Deploy and manage a Kubernetes cluster with monitoring",
        ],
    },
    "Software Development": {
        "roles": [
            "Software Developer",
            "Application Developer",
            "Java Developer",
            "Python Developer",
            "Systems Analyst",
        ],
        "skills": [
            "Java / Python",
            "Object-Oriented Programming",
            "SQL / Databases",
            "Data Structures & Algorithms",
            "Software Engineering",
            "Git / Version Control",
            "Operating Systems",
            "Testing",
        ],
        "certifications": [
            "Oracle Certified Professional: Java SE Developer",
            "Microsoft Certified: Azure Developer Associate",
            "ISTQB Certified Tester",
        ],
        "project_suggestions": [
            "Build a complete software application with testing and documentation",
            "Develop a CLI tool or utility that solves a real problem",
            "Contribute to an open-source project with meaningful pull requests",
        ],
    },
    "Business Analytics": {
        "roles": [
            "Business Analyst",
            "Data Analyst",
            "BI Analyst",
            "Operations Analyst",
            "Research Analyst",
        ],
        "skills": [
            "SQL",
            "Excel / Spreadsheets",
            "Data Visualization",
            "Statistics",
            "Business Acumen",
            "Requirements Gathering",
            "Python / R",
            "Power BI / Tableau",
        ],
        "certifications": [
            "Google Data Analytics Professional Certificate",
            "Microsoft Certified: Data Analyst Associate",
            "IIBA Certified Business Analysis Professional (CBAP)",
        ],
        "project_suggestions": [
            "Analyze a real business dataset and present actionable insights",
            "Build an interactive dashboard for a fictional business scenario",
            "Conduct a requirements analysis project for a software system",
        ],
    },
    "Operations": {
        "roles": [
            "Operations Manager",
            "Supply Chain Analyst",
            "Project Manager",
            "Process Improvement Specialist",
            "Logistics Coordinator",
        ],
        "skills": [
            "Project Management",
            "Supply Chain Management",
            "Process Optimization",
            "Data Analysis",
            "ERP Systems",
            "Inventory Management",
            "Lean / Six Sigma",
            "Communication",
        ],
        "certifications": [
            "PMP (Project Management Professional)",
            "Certified Supply Chain Professional (CSCP)",
            "Lean Six Sigma Green Belt",
        ],
        "project_suggestions": [
            "Map and optimize a business process using flowcharts and metrics",
            "Conduct a supply chain analysis project with real data",
            "Manage a small team project using Agile/Scrum methodology",
        ],
    },
    "Marketing": {
        "roles": [
            "Marketing Executive",
            "Brand Manager",
            "Market Research Analyst",
            "Content Strategist",
            "Product Marketing Manager",
        ],
        "skills": [
            "Consumer Behavior",
            "Market Research",
            "Digital Marketing",
            "Brand Management",
            "Content Creation",
            "SEO / SEM",
            "Social Media Marketing",
            "Business Communication",
        ],
        "certifications": [
            "Google Ads Certification",
            "HubSpot Inbound Marketing Certification",
            "Meta Certified Marketing Science Professional",
        ],
        "project_suggestions": [
            "Create a complete marketing plan for a product launch",
            "Run a social media campaign and analyze performance metrics",
            "Conduct primary market research with surveys and data analysis",
        ],
    },
    "Digital Marketing": {
        "roles": [
            "Digital Marketing Specialist",
            "SEO Analyst",
            "Social Media Manager",
            "Content Marketer",
            "Growth Hacker",
        ],
        "skills": [
            "SEO / SEM",
            "Social Media Marketing",
            "Content Marketing",
            "Google Analytics",
            "Email Marketing",
            "PPC Advertising",
            "Marketing Automation",
            "Data Analysis",
        ],
        "certifications": [
            "Google Digital Marketing & E-commerce Certificate",
            "HubSpot Content Marketing Certification",
            "Meta Social Media Marketing Professional Certificate",
        ],
        "project_suggestions": [
            "Build and optimize a website for SEO with measurable traffic growth",
            "Run a Google Ads campaign and analyze ROI",
            "Create a content marketing calendar and measure engagement",
        ],
    },
    "Banking": {
        "roles": [
            "Banking Analyst",
            "Credit Analyst",
            "Relationship Manager",
            "Treasury Analyst",
            "Risk Analyst",
        ],
        "skills": [
            "Financial Accounting",
            "Banking Operations",
            "Credit Analysis",
            "Risk Management",
            "Regulatory Compliance",
            "Financial Modeling",
            "Investment Analysis",
            "Business Economics",
        ],
        "certifications": [
            "JAIIB (Junior Associate of the Indian Institute of Bankers)",
            "Certified Banking & Credit Analyst (CBCA)",
            "Financial Risk Manager (FRM)",
        ],
        "project_suggestions": [
            "Build a financial model for loan amortization analysis",
            "Analyze a bank's financial statements and assess credit risk",
            "Create a risk assessment report for a mock investment portfolio",
        ],
    },
    "Finance": {
        "roles": [
            "Financial Analyst",
            "Investment Analyst",
            "Equity Research Analyst",
            "Wealth Manager",
            "Corporate Finance Analyst",
        ],
        "skills": [
            "Financial Modeling",
            "Valuation Techniques",
            "Investment Analysis",
            "Accounting",
            "Risk Management",
            "Excel / Financial Tools",
            "Business Economics",
            "Regulatory Knowledge",
        ],
        "certifications": [
            "CFA (Chartered Financial Analyst) Level I",
            "Financial Modeling & Valuation Analyst (FMVA)",
            "NISM Certification",
        ],
        "project_suggestions": [
            "Build a DCF valuation model for a publicly traded company",
            "Analyze and compare investment portfolios using risk-return metrics",
            "Create a personal finance tracking dashboard",
        ],
    },
    "Human Resources": {
        "roles": [
            "HR Executive",
            "Talent Acquisition Specialist",
            "HR Business Partner",
            "Training & Development Specialist",
            "Compensation Analyst",
        ],
        "skills": [
            "Recruitment & Selection",
            "Employee Relations",
            "Performance Management",
            "Organizational Behavior",
            "Labor Law",
            "HR Analytics",
            "Training Design",
            "Business Communication",
        ],
        "certifications": [
            "SHRM Certified Professional (SHRM-CP)",
            "Professional in Human Resources (PHR)",
            "Google People Analytics Professional Certificate",
        ],
        "project_suggestions": [
            "Design an employee onboarding process flow with KPIs",
            "Conduct a salary benchmarking analysis for a specific role",
            "Create a training program proposal based on identified skill gaps",
        ],
    },
    "Sales": {
        "roles": [
            "Sales Executive",
            "Business Development Executive",
            "Key Account Manager",
            "Sales Manager",
            "Channel Sales Executive",
        ],
        "skills": [
            "Negotiation",
            "Client Relationship Management",
            "Consumer Behavior",
            "Sales Analytics",
            "Business Communication",
            "Product Knowledge",
            "CRM Tools",
            "Market Research",
        ],
        "certifications": [
            "Certified Professional Sales Person (CPSP)",
            "HubSpot Sales Software Certification",
            "Salesforce Certified Administrator",
        ],
        "project_suggestions": [
            "Develop a sales pitch deck and present it to a mock client panel",
            "Analyze sales data to identify trends and recommend strategies",
            "Create a CRM workflow for lead tracking and conversion",
        ],
    },
    "Entrepreneurship": {
        "roles": [
            "Startup Founder",
            "Business Development Manager",
            "Product Manager",
            "Innovation Consultant",
            "Venture Analyst",
        ],
        "skills": [
            "Business Planning",
            "Market Research",
            "Financial Planning",
            "Pitch Deck Creation",
            "Strategic Management",
            "Leadership",
            "Innovation",
            "Project Management",
        ],
        "certifications": [
            "Y Combinator Startup School",
            "Google Entrepreneurship Certificate",
            "Coursera Entrepreneurship Specialization",
        ],
        "project_suggestions": [
            "Write a complete business plan with financial projections",
            "Build a minimum viable product (MVP) and test with users",
            "Pitch your startup idea at a college or local pitch event",
        ],
    },
}


def _round(value: Optional[float], ndigits: int = 1) -> Optional[float]:
    return None if value is None else round(value, ndigits)


def _float_or_none(value: Any) -> Optional[float]:
    """Normalize DB numeric types (asyncpg returns NUMERIC as Decimal) to float."""
    return None if value is None else float(value)


def subject_is_relevant(preferred_domain: Optional[str], subject_name: str) -> bool:
    """Whether a subject counts as domain-relevant for the preferred domain.

    Deterministic substring matching (case-insensitive) against the
    ``DOMAIN_SUBJECT_KEYWORDS`` map. Unknown domains match nothing so the
    alignment stays explainable instead of guessing.
    """
    if not preferred_domain:
        return False
    keywords = DOMAIN_SUBJECT_KEYWORDS.get(preferred_domain, [])
    haystack = (subject_name or "").lower()
    return any(keyword in haystack for keyword in keywords)


# ---------------------------------------------------------------------------
# Domain alignment
# ---------------------------------------------------------------------------


def _alignment_band(score: float) -> str:
    if score >= settings.CAREER_ALIGNMENT_STRONG_MIN:
        return "Strong"
    if score >= settings.CAREER_ALIGNMENT_GOOD_MIN:
        return "Good"
    if score >= settings.CAREER_ALIGNMENT_DEVELOPING_MIN:
        return "Developing"
    return "Needs Attention"


def compute_domain_alignment(
    preferred_domain: Optional[str],
    completed_subjects: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Domain alignment: share of completed subjects relevant to the domain.

    ``completed_subjects`` must be the latest-attempt completed rows (each
    carrying at least ``subject_name`` and ``percentage``). Rows with a missing
    ``percentage`` are ignored (a pending result is never treated as zero).
    """
    aligned: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []
    for row in completed_subjects:
        if row.get("percentage") is None:
            continue
        relevant = subject_is_relevant(preferred_domain, row.get("subject_name", ""))
        if relevant:
            aligned.append(
                {
                    **row,
                    "relevant": True,
                    "reason": f"Relevant to {preferred_domain}",
                }
            )
        else:
            other.append(
                {
                    **row,
                    "relevant": False,
                    "reason": f"Not directly related to {preferred_domain}",
                }
            )

    total = len(aligned) + len(other)
    if total == 0 or not preferred_domain:
        return {
            "available": False,
            "score": None,
            "band": None,
            "aligned_subjects": aligned,
            "other_subjects": other,
            "aligned_count": len(aligned),
            "total_completed": total,
            "reasons": [
                (
                    "No preferred career domain recorded yet."
                    if not preferred_domain
                    else "No completed subjects available to measure alignment."
                )
            ],
        }

    score = round(len(aligned) / total * 100, 1)
    return {
        "available": True,
        "score": score,
        "band": _alignment_band(score),
        "aligned_subjects": aligned,
        "other_subjects": other,
        "aligned_count": len(aligned),
        "total_completed": total,
        "reasons": [
            f"{len(aligned)} of {total} completed subjects are relevant to {preferred_domain}."
        ],
    }


# ---------------------------------------------------------------------------
# Career Readiness score
# ---------------------------------------------------------------------------


def _academic_component(completed_percentages: List[float]) -> Dict[str, Any]:
    if not completed_percentages:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ACADEMIC_WEIGHT,
            "reason": "No completed subject results yet.",
        }
    avg = sum(completed_percentages) / len(completed_percentages)
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, avg)), 1),
        "weight": settings.CAREER_ACADEMIC_WEIGHT,
        "reason": f"Completed subjects average {avg:.1f}%.",
    }


def _consistency_component(
    completed_summaries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sgpas = [
        s["sgpa"]
        for s in completed_summaries
        if s.get("sgpa") is not None
    ]
    if len(sgpas) < 2:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_CONSISTENCY_WEIGHT,
            "reason": "Not enough completed semesters to measure consistency.",
        }
    sd = statistics.pstdev(sgpas)
    score = max(
        0.0,
        min(100.0, 100.0 - sd * settings.CAREER_CONSISTENCY_SD_SCALE),
    )
    return {
        "available": True,
        "score": round(score, 1),
        "weight": settings.CAREER_CONSISTENCY_WEIGHT,
        "reason": (
            f"SGPA varied by {sd:.2f} across {len(sgpas)} completed semesters."
        ),
    }


def _alignment_component(alignment_score: Optional[float]) -> Dict[str, Any]:
    if alignment_score is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ALIGNMENT_WEIGHT,
            "reason": "Domain alignment could not be measured yet.",
        }
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, alignment_score)), 1),
        "weight": settings.CAREER_ALIGNMENT_WEIGHT,
        "reason": f"Domain alignment is {alignment_score:.1f}%.",
    }


def _attendance_component(attendance_pct: Optional[float]) -> Dict[str, Any]:
    if attendance_pct is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_ATTENDANCE_WEIGHT,
            "reason": "Attendance data is not available yet.",
        }
    return {
        "available": True,
        "score": round(max(0.0, min(100.0, attendance_pct)), 1),
        "weight": settings.CAREER_ATTENDANCE_WEIGHT,
        "reason": f"Attendance is {attendance_pct:.1f}%.",
    }


def _internship_component(internship_completed: Optional[str]) -> Dict[str, Any]:
    if internship_completed is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_INTERNSHIP_WEIGHT,
            "reason": "No internship status recorded in the career survey.",
        }
    score = 100.0 if internship_completed == "Yes" else 0.0
    return {
        "available": True,
        "score": score,
        "weight": settings.CAREER_INTERNSHIP_WEIGHT,
        "reason": (
            "Internship completed."
            if score > 0
            else "No internship completed yet — a key placement input."
        ),
    }


def _readiness_component(placement_readiness_level: Optional[str]) -> Dict[str, Any]:
    if placement_readiness_level is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_READINESS_WEIGHT,
            "reason": "No self-assessed placement readiness recorded yet.",
        }
    score = PLACEMENT_READINESS_SCORES.get(placement_readiness_level)
    if score is None:
        return {
            "available": False,
            "score": None,
            "weight": settings.CAREER_READINESS_WEIGHT,
            "reason": f"Placement readiness level '{placement_readiness_level}' is not mapped.",
        }
    return {
        "available": True,
        "score": score,
        "weight": settings.CAREER_READINESS_WEIGHT,
        "reason": f"Self-assessed placement readiness: {placement_readiness_level}.",
    }


def _career_band(score: float) -> str:
    if score >= settings.CAREER_READINESS_STRONG_MIN:
        return "Strong"
    if score >= settings.CAREER_READINESS_GOOD_MIN:
        return "Good"
    if score >= settings.CAREER_READINESS_DEVELOPING_MIN:
        return "Developing"
    return "Needs Attention"


def compute_career_readiness(
    completed_percentages: List[float],
    completed_summaries: List[Dict[str, Any]],
    alignment_score: Optional[float],
    attendance_pct: Optional[float],
    internship_completed: Optional[str],
    placement_readiness_level: Optional[str],
) -> Dict[str, Any]:
    """Deterministic career readiness score (0-100) + components + reasons."""
    completed_percentages = [
        float(value) for value in completed_percentages if value is not None
    ]
    completed_summaries = [
        {
            **summary,
            "sgpa": _float_or_none(summary.get("sgpa")),
            "semester_percentage": _float_or_none(summary.get("semester_percentage")),
        }
        for summary in completed_summaries
    ]
    components = {
        "academic": _academic_component(completed_percentages),
        "consistency": _consistency_component(completed_summaries),
        "alignment": _alignment_component(alignment_score),
        "attendance": _attendance_component(_float_or_none(attendance_pct)),
        "internship": _internship_component(internship_completed),
        "readiness": _readiness_component(placement_readiness_level),
    }

    available = [comp for comp in components.values() if comp["available"]]
    if len(available) < settings.CAREER_READINESS_AVAILABLE_COMPONENT_MIN:
        return {
            "available": False,
            "score": None,
            "band": None,
            "components": components,
            "reasons": [
                "Not enough data is available yet to compute a career readiness score."
            ],
        }

    weight_sum = sum(comp["weight"] for comp in available)
    score = (
        sum(comp["score"] * comp["weight"] for comp in available) / weight_sum
        if weight_sum > 0
        else None
    )
    if score is None:
        return {
            "available": True,
            "score": None,
            "band": None,
            "components": components,
            "reasons": [],
        }

    reasons: List[str] = []
    for key in (
        "academic",
        "consistency",
        "alignment",
        "attendance",
        "internship",
        "readiness",
    ):
        comp = components[key]
        if comp["available"]:
            reasons.append(comp["reason"])

    return {
        "available": True,
        "score": round(score, 1),
        "band": _career_band(score),
        "components": components,
        "reasons": reasons,
    }
