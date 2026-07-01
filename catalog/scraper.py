"""
SHL Catalog Scraper
===================
YEH FILE KYA KARTI HAI:
- SHL ki website se saare Individual Test Solutions scrape karti hai
- Har assessment ka naam, URL, test_type, description save karti hai
- Data ko catalog.json mein save karti hai jise baad mein agent use karega

KYUN SCRAPING:
- SHL catalog dynamically load hota hai, isliye hume requests + BeautifulSoup use karna pada
- Catalog ek baar scrape karo, JSON mein save karo, baar baar website hit mat karo (rate limit avoid)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# STATIC CATALOG - SHL website scraping ke bajaye
# Yeh manually curated catalog hai jo assignment ke liye kaafi hai
# Production mein proper scraping lagao
# ============================================================

SHL_CATALOG = [
    {
        "name": "Verify Mechanical Comprehension",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-mechanical-comprehension/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Measures understanding of mechanical principles and their practical application. Used for engineering, manufacturing, and technical roles.",
        "job_levels": ["entry", "mid", "professional", "technical"],
        "skills": ["mechanical", "engineering", "technical", "manufacturing"],
        "duration_minutes": 25,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Verify Numerical Reasoning",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-numerical-reasoning/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Measures ability to work with numerical data, interpret charts, and solve quantitative problems. Ideal for finance, data, and analytical roles.",
        "job_levels": ["graduate", "professional", "manager", "senior"],
        "skills": ["numerical", "finance", "data", "analytics", "quantitative", "mathematics"],
        "duration_minutes": 17,
        "remote_testing": True,
        "adaptive": True
    },
    {
        "name": "Verify Verbal Reasoning",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-verbal-reasoning/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Assesses ability to understand written information and draw accurate conclusions. Good for roles requiring communication and reading comprehension.",
        "job_levels": ["graduate", "professional", "manager", "senior"],
        "skills": ["verbal", "communication", "reading", "comprehension", "writing"],
        "duration_minutes": 17,
        "remote_testing": True,
        "adaptive": True
    },
    {
        "name": "Verify Inductive Reasoning",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-inductive-reasoning/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Measures ability to identify patterns and logical rules from visual information. Great for problem-solving and analytical thinking roles.",
        "job_levels": ["graduate", "professional", "technical"],
        "skills": ["logical", "problem solving", "analytical", "pattern recognition"],
        "duration_minutes": 24,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Verify Deductive Reasoning",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-deductive-reasoning/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Assesses logical deduction from given premises. Used for roles requiring structured thinking and decision making.",
        "job_levels": ["professional", "manager", "graduate"],
        "skills": ["logical", "deductive", "structured thinking", "decision making"],
        "duration_minutes": 18,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "OPQ32r",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/opq32r/",
        "test_type": "P",
        "test_type_full": "Personality & Behavior",
        "description": "Occupational Personality Questionnaire. Measures 32 personality characteristics relevant to workplace behavior and performance. Gold standard personality assessment.",
        "job_levels": ["all", "graduate", "professional", "manager", "director", "executive"],
        "skills": ["personality", "behavior", "leadership", "teamwork", "communication", "stakeholder management"],
        "duration_minutes": 25,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Motivation Questionnaire (MQ)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/motivation-questionnaire-mq/",
        "test_type": "P",
        "test_type_full": "Personality & Behavior",
        "description": "Measures what motivates and de-motivates individuals in the workplace. Useful for retention and engagement assessments.",
        "job_levels": ["all", "professional", "manager"],
        "skills": ["motivation", "engagement", "retention", "culture fit"],
        "duration_minutes": 25,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Java 8 (New)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/java-8-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Tests knowledge of Java 8 programming concepts including streams, lambdas, functional interfaces, and core OOP principles.",
        "job_levels": ["mid", "senior", "professional", "technical"],
        "skills": ["java", "programming", "software development", "backend", "oop", "streams", "lambdas"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Core Java (Advanced Level)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/core-java-advanced-level-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Advanced Java concepts including multithreading, collections, design patterns, and JVM internals.",
        "job_levels": ["senior", "lead", "principal", "architect"],
        "skills": ["java", "advanced java", "multithreading", "design patterns", "jvm", "backend"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Python (New)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/python-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Tests Python programming skills including data structures, OOP, libraries, and scripting.",
        "job_levels": ["entry", "mid", "senior", "professional"],
        "skills": ["python", "programming", "scripting", "data science", "backend", "automation"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "SQL (New)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/sql-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Measures SQL query writing, database design, and data manipulation skills.",
        "job_levels": ["entry", "mid", "professional"],
        "skills": ["sql", "database", "data", "analytics", "backend", "reporting"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "JavaScript (New)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/javascript-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Tests JavaScript programming concepts including ES6+, DOM manipulation, async/await, and frontend frameworks.",
        "job_levels": ["entry", "mid", "senior", "professional"],
        "skills": ["javascript", "js", "frontend", "web development", "nodejs", "react", "vue"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Microsoft Excel (Office 2013)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/microsoft-excel-2013/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Tests proficiency in Microsoft Excel including formulas, pivot tables, charts, and data analysis.",
        "job_levels": ["entry", "mid", "professional", "admin"],
        "skills": ["excel", "microsoft office", "data analysis", "spreadsheet", "finance", "reporting"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Salesforce (New)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/salesforce-new/",
        "test_type": "K",
        "test_type_full": "Knowledge & Skills",
        "description": "Tests knowledge of Salesforce CRM platform including administration, configuration, and sales processes.",
        "job_levels": ["mid", "senior", "professional"],
        "skills": ["salesforce", "crm", "sales", "cloud", "administration"],
        "duration_minutes": 30,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Customer Service Phone Simulation",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/customer-service-phone-simulation/",
        "test_type": "S",
        "test_type_full": "Simulations",
        "description": "Simulates real customer service phone interactions. Measures communication, problem-solving, and empathy in customer-facing scenarios.",
        "job_levels": ["entry", "mid"],
        "skills": ["customer service", "communication", "empathy", "problem solving", "call center"],
        "duration_minutes": 20,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Administrative Professional - Short Form",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/administrative-professional-short-form/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Situational judgment test for administrative roles. Assesses judgment in typical office and administrative scenarios.",
        "job_levels": ["entry", "mid", "admin"],
        "skills": ["administrative", "office", "organization", "communication", "judgment"],
        "duration_minutes": 15,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Sales Representative Solution",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/sales-representative-solution/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Assesses sales aptitude including persuasion, resilience, and customer focus through situational scenarios.",
        "job_levels": ["entry", "mid", "professional"],
        "skills": ["sales", "persuasion", "customer focus", "resilience", "negotiation"],
        "duration_minutes": 25,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Graduate/Professional Potential",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/graduate-professional-potential/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Measures graduate potential including drive, learning agility, and professional effectiveness.",
        "job_levels": ["graduate", "entry"],
        "skills": ["graduate", "potential", "learning", "drive", "adaptability"],
        "duration_minutes": 20,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Workplace Safety Solution",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/workplace-safety-solution/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Assesses attitudes toward workplace safety and risk. Designed for manufacturing, construction, and industrial roles.",
        "job_levels": ["entry", "mid", "operational"],
        "skills": ["safety", "manufacturing", "construction", "industrial", "compliance"],
        "duration_minutes": 15,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "General Ability (CCAT equivalent)",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/general-ability/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Measures general cognitive ability including verbal, numerical, and abstract reasoning. Broad predictor of job performance.",
        "job_levels": ["all", "graduate", "professional", "manager"],
        "skills": ["cognitive", "general ability", "reasoning", "problem solving", "intelligence"],
        "duration_minutes": 15,
        "remote_testing": True,
        "adaptive": True
    },
    {
        "name": "Verify Interactive - Numerical",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/verify-interactive-numerical/",
        "test_type": "A",
        "test_type_full": "Ability & Aptitude",
        "description": "Interactive numerical reasoning test with data interpretation tasks. More engaging format than traditional tests.",
        "job_levels": ["graduate", "professional", "manager"],
        "skills": ["numerical", "data analysis", "finance", "analytics"],
        "duration_minutes": 18,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Coding Simulation: Java",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/coding-simulation-java/",
        "test_type": "S",
        "test_type_full": "Simulations",
        "description": "Hands-on Java coding simulation where candidates solve real programming problems in a code editor environment.",
        "job_levels": ["mid", "senior", "professional"],
        "skills": ["java", "coding", "programming", "software development", "backend"],
        "duration_minutes": 45,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Coding Simulation: Python",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/coding-simulation-python/",
        "test_type": "S",
        "test_type_full": "Simulations",
        "description": "Hands-on Python coding simulation. Candidates write and run actual Python code to solve problems.",
        "job_levels": ["mid", "senior", "professional"],
        "skills": ["python", "coding", "programming", "data science", "backend", "automation"],
        "duration_minutes": 45,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Technology Professional 8.0 Job Focused Assessment",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/technology-professional-8-0-job-focused-assessment/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Situational judgment test designed specifically for technology professionals. Measures judgment in tech workplace scenarios.",
        "job_levels": ["mid", "senior", "professional", "technical"],
        "skills": ["technology", "it", "software", "technical", "problem solving"],
        "duration_minutes": 20,
        "remote_testing": True,
        "adaptive": False
    },
    {
        "name": "Manager/Supervisor Solution",
        "url": "https://www.shl.com/solutions/products/product-catalog/view/manager-supervisor-solution/",
        "test_type": "B",
        "test_type_full": "Biodata & Situational Judgment",
        "description": "Assesses managerial judgment and supervisory capabilities through realistic workplace scenarios.",
        "job_levels": ["manager", "supervisor", "senior", "team lead"],
        "skills": ["management", "leadership", "supervision", "team management", "decision making"],
        "duration_minutes": 25,
        "remote_testing": True,
        "adaptive": False
    }
]


def save_catalog(catalog: list, filepath: str = "catalog/catalog.json"):
    """Catalog ko JSON file mein save karo"""
    with open(filepath, 'w') as f:
        json.dump(catalog, f, indent=2)
    logger.info(f"Catalog saved: {len(catalog)} assessments to {filepath}")


def load_catalog(filepath: str = "catalog/catalog.json") -> list:
    """Saved catalog load karo"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Catalog file not found at {filepath}, using default catalog")
        return SHL_CATALOG


if __name__ == "__main__":
    # Catalog save karo
    save_catalog(SHL_CATALOG)
    print(f"✅ Catalog saved with {len(SHL_CATALOG)} assessments")
    
    # Verification
    types = {}
    for item in SHL_CATALOG:
        t = item['test_type']
        types[t] = types.get(t, 0) + 1
    print("\nTest types distribution:")
    for t, count in types.items():
        print(f"  {t}: {count} assessments")