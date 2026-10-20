#!/usr/bin/env python3
"""
Job Discovery Master Data Management (MDM) Builder & Super In-Depth Headhunter
=============================================================================
Synthesizes:
1. Baseline MDM dataset (master_companies_mdm.csv)
2. Top 100 Global Pharma, Biotech, MedTech, CRO/CDMO, and HealthTech GCCs in India
3. Top Adjacent Industry Companies & GCCs in India:
   - HealthTech Platforms & Bio-Informatics (Innovaccer, CitiusTech, Indegene, Athenahealth, Veeva Systems, Flatiron Health)
   - AI & Data Science Consultancies (Tiger Analytics, Tredence, Fractal Analytics, LatentView, TheMathCompany, Quantiphi)
   - Cloud Lakehouse & AI Infrastructure (Snowflake, Databricks, Confluent, MongoDB, Elastic, Fivetran, Dremio, Cloudera)
   - E-Commerce Logistics, D2C & AdTech (Flipkart, Swiggy, Zomato, Blinkit, Zepto, Delhivery, Shadowfax, Shiprocket, InMobi)
   - Quant & Algorithmic Trading / WealthTech (Tower Research, WorldQuant, Jump Trading, Graviton, Quadeye, Razorpay, CRED, Groww)
   - Enterprise SaaS, Workflow & Observability (Postman, BrowserStack, Hasura, Chargebee, Freshworks, Zoho, Darwinbox, Sprinklr)
4. Candidate Persona Alignment: Dynamic candidate persona from .env / profile template
   (Healthcare Commercial Analytics, Airflow/Snowflake/SQL Data Engineering, E-com Logistics, Valuation)
5. Token Benchmarking Metrics: Quantifies prompt, completion, and total tokens at each synthesis stage.

Outputs (persisted in job_discovery/):
- master_companies_mdm.csv  (Complete tabular MDM without personal LinkedIn links)
- master_companies_mdm.json (Complete programmatic JSON dataset)
- README.md                 (MDM Master Guide, Token Benchmarks & Domain Statistics)
- pharma_medtech_lifesciences.md (The Definitive 125+ Pharma, MedTech & HealthTech India GCC Guide)
- all_companies_catalog.md  (Complete employer directory across 7 strategic pillars)
- india_gcc_landscape.md    (Full directory of 200+ Global Capability Centers in India)
"""

from __future__ import annotations

import csv
import json
import os
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "job_discovery"
OUTPUT_DIR.mkdir(exist_ok=True)

BASELINE_CSV = OUTPUT_DIR / "master_companies_mdm.csv"

# ── TOP 100 GLOBAL PHARMA, MEDTECH & LIFE SCIENCES GCCs / INDIA HUBS ────────
TOP_100_PHARMA_MEDTECH_HUBS = [
    # Global Biopharma & Big Pharma Giants
    {"company": "Novartis", "gcc": "Novartis Corporate Center (NOCC)", "loc": "Hyderabad, Mumbai", "focus": "Global R&D, Clinical Data Science, Commercial Analytics, AI Drug Discovery, Supply Chain", "portal": "https://www.novartis.com/careers/career-search"},
    {"company": "AstraZeneca", "gcc": "AstraZeneca India Global Operations & R&D Center", "loc": "Bengaluru, Chennai", "focus": "Global IT, Data Science, AI in Drug Development, Commercial Operations Analytics", "portal": "https://careers.astrazeneca.com"},
    {"company": "Roche", "gcc": "Roche Information Solutions & Digital Diagnostics", "loc": "Pune, Hyderabad", "focus": "Digital Diagnostics R&D, Healthcare Data Systems, Personalized Healthcare Analytics", "portal": "https://careers.roche.com"},
    {"company": "Pfizer", "gcc": "Pfizer Global Capability Centre & Clinical R&D Hub", "loc": "Chennai, Mumbai", "focus": "Global Drug Development, Clinical Analytics, Commercial Operations, Regulatory Science", "portal": "https://www.pfizer.com/about/careers"},
    {"company": "Bristol Myers Squibb", "gcc": "BMS Innovation Hub & Biocon BMS R&D Center (BBRC)", "loc": "Hyderabad, Bengaluru", "focus": "Commercial Analytics, Clinical Data Science, Drug Development Technology, Digital Health", "portal": "https://careers.bms.com"},
    {"company": "Sanofi", "gcc": "Sanofi Global Capability Center (CCPL)", "loc": "Hyderabad, Mumbai", "focus": "End-to-End Clinical Data Management, Artificial Intelligence, Commercial Strategy, Digital Health", "portal": "https://www.sanofi.com/en/careers"},
    {"company": "Takeda", "gcc": "Takeda Innovation Capability Center (ICC)", "loc": "Bengaluru, Hyderabad", "focus": "Data & Digital Transformation, AI-driven Drug Discovery, Commercial Data Engineering", "portal": "https://www.takeda.com/careers/"},
    {"company": "Amgen", "gcc": "Amgen Technology and Innovation Centre", "loc": "Hyderabad", "focus": "Digital Tech, AI/ML for Biologics, Clinical Trial Analytics, Commercial Data Architecture", "portal": "https://careers.amgen.com"},
    {"company": "Eli Lilly", "gcc": "Eli Lilly Global Technology Centers", "loc": "Bengaluru, Hyderabad", "focus": "AI/Cloud Analytics, Clinical Informatics, Commercial Operations, Global R&D IT", "portal": "https://careers.lilly.com"},
    {"company": "Merck KGaA (EMD Group)", "gcc": "Merck Global Capability Centre (MGCC)", "loc": "Bengaluru, Mumbai", "focus": "Digital Health, Healthcare Commercial Data Systems, Life Science Analytics, Process Optimization", "portal": "https://www.merckgroup.com/en/careers.html"},
    {"company": "Bayer", "gcc": "Bayer Global Business Services & Tech Hub", "loc": "Hyderabad, Thane/Mumbai", "focus": "Global Clinical Operations, Pharma Data Science, Supply Chain Analytics, Digital Crop/Pharma", "portal": "https://www.bayer.com/en/career"},
    {"company": "Johnson & Johnson", "gcc": "J&J Global Capability & Tech Services", "loc": "Bengaluru, Mumbai", "focus": "MedTech Software, Clinical Data Engineering, Supply Chain Visibility, Digital Surgery", "portal": "https://www.careers.jnj.com"},
    {"company": "GSK (GlaxoSmithKline)", "gcc": "GSK Global Capability Hubs", "loc": "Bengaluru, Mumbai", "focus": "Biostatistics, Vaccines & Specialty Medicines Data Systems, Commercial Analytics", "portal": "https://www.gsk.com/en-gb/careers/"},
    {"company": "AbbVie", "gcc": "AbbVie India Commercial & Clinical Data Hub", "loc": "Bengaluru, Mumbai", "focus": "Specialty Pharma Commercial Analytics, Clinical Trial Operations, Medical Affairs Data", "portal": "https://careers.abbvie.com"},
    {"company": "Novo Nordisk", "gcc": "Novo Nordisk Global Business Services (GBS)", "loc": "Bengaluru", "focus": "Global Biostatistics, Safety Science, Commercial Analytics, Diabetes & Obesity Clinical Data", "portal": "https://www.novonordisk.co.in/careers.html"},
    {"company": "Boehringer Ingelheim", "gcc": "Boehringer Ingelheim India Digital & Commercial Hub", "loc": "Mumbai", "focus": "Human Pharma Commercial Strategy, Clinical Operations, Animal Health Analytics", "portal": "https://www.boehringer-ingelheim.com/careers"},
    {"company": "Gilead Sciences", "gcc": "Gilead India Clinical & Commercial Operations", "loc": "Mumbai", "focus": "Antiviral Commercial Analytics, Access Programs, Clinical Regulatory Informatics", "portal": "https://www.gilead.com/careers"},
    {"company": "Biogen", "gcc": "Biogen India Analytics & Digital Health Hub", "loc": "Bengaluru", "focus": "Neuroscience Commercial Analytics, Real-World Data, Digital Biomarkers", "portal": "https://www.biogen.com/careers.html"},
    {"company": "Regeneron Pharmaceuticals", "gcc": "Regeneron Clinical Data Systems", "loc": "Bengaluru", "focus": "Genomic Data Processing, Clinical Trial Systems, Commercial Execution Analytics", "portal": "https://careers.regeneron.com"},
    {"company": "Vertex Pharmaceuticals", "gcc": "Vertex Global Clinical Informatics", "loc": "Bengaluru, Hyderabad", "focus": "Cystic Fibrosis & Genetic Disease Commercial Analytics, Clinical Data Architecture", "portal": "https://www.vrtx.com/careers"},
    {"company": "Viatris", "gcc": "Viatris Commercial Analytics & Global Shared Services", "loc": "Hyderabad, Bengaluru, Mumbai", "focus": "Generics & Biosimilars Commercial Analytics, Supply Chain IT, Financial Planning", "portal": "https://www.viatris.com/en/careers"},
    {"company": "Teva Pharmaceuticals", "gcc": "Teva Global R&D & Tech Center", "loc": "Mumbai, Noida/NCR", "focus": "Global Regulatory Affairs, Generic Commercial Analytics, Clinical Data Management", "portal": "https://www.tevapharm.com/careers/"},
    {"company": "Organon", "gcc": "Organon Global Shared Services", "loc": "Hyderabad", "focus": "Women's Health Commercial Analytics, Supply Chain Optimization, Global Data Warehousing", "portal": "https://www.organon.com/careers/"},
    {"company": "Jazz Pharmaceuticals", "gcc": "Jazz Life Sciences Analytics Hub", "loc": "Hyderabad", "focus": "Neuroscience & Oncology Commercial Analytics, Data Science, Medical Affairs", "portal": "https://www.jazzpharma.com/careers/"},
    {"company": "CSL Behring", "gcc": "CSL Global Technology Center", "loc": "Bengaluru", "focus": "Plasma & Rare Disease Data Science, Biotherapies Supply Chain Engineering", "portal": "https://www.cslbehring.com/careers"},
    {"company": "Grifols", "gcc": "Grifols Biopharma Analytics Hub", "loc": "Bengaluru", "focus": "Plasma Derivatives Analytics, Commercial Market Access, Clinical Data Pipelines", "portal": "https://www.grifols.com/en/careers"},
    {"company": "Servier", "gcc": "Servier India Research & Commercial Hub", "loc": "Mumbai", "focus": "Cardiovascular & Oncology Commercial BI, Clinical Data Governance", "portal": "https://servier.com/en/careers/"},
    {"company": "Menarini Group", "gcc": "Menarini Asia-Pacific Commercial Analytics Hub", "loc": "Mumbai", "focus": "Commercial Market Dynamics, Multi-channel Campaign Analytics, HCP Engagement", "portal": "https://www.menarini.com/en-us/careers"},
    {"company": "Daiichi Sankyo", "gcc": "Daiichi Sankyo India R&D & Operations", "loc": "Gurugram/NCR", "focus": "Antibody Drug Conjugate (ADC) Analytics, Global Data Systems, Clinical Operations", "portal": "https://www.daiichisankyo.com/careers/"},
    {"company": "Astellas Pharma", "gcc": "Astellas India Data & Digital Tech Hub", "loc": "Mumbai, Bengaluru", "focus": "Commercial Strategy & Access, Global Medical Affairs Analytics, Digital Therapeutics", "portal": "https://www.astellas.com/en/careers"},
    {"company": "Eisai", "gcc": "Eisai India Knowledge & Development Centre", "loc": "Visakhapatnam, Mumbai", "focus": "Neurology & Oncology Clinical Analytics, API Process R&D, Global Shared Services", "portal": "https://www.eisai.com/careers/index.html"},
    {"company": "Otsuka Pharmaceutical", "gcc": "Otsuka Global Development Hub", "loc": "Mumbai, Ahmedabad", "focus": "Clinical Development Systems, Nutraceutical Commercial BI, Medical Data Management", "portal": "https://www.otsuka.co.jp/en/company/careers/"},
    {"company": "UCB", "gcc": "UCB India Biopharma Digital Solutions", "loc": "Bengaluru", "focus": "Immunology & Neurology Digital Solutions, Commercial Insights, Big Data Ingestion", "portal": "https://www.ucb.com/careers"},
    {"company": "BioMarin Pharmaceutical", "gcc": "BioMarin Rare Disease Analytics Hub", "loc": "Hyderabad, Bengaluru", "focus": "Gene Therapy Data Pipelines, Rare Disease Commercial Analytics, Real-World Evidence", "portal": "https://careers.biomarin.com"},
    {"company": "Kyowa Kirin", "gcc": "Kyowa Kirin Asia-Pacific Commercial Analytics", "loc": "Mumbai", "focus": "Antibody Technology Commercial Analytics, Global Market Access Modeling", "portal": "https://www.kyowakirin.com/careers/"},

    # MedTech, Medical Devices & Surgical Robotics
    {"company": "Medtronic", "gcc": "Medtronic Engineering & Innovation Center (MEIC)", "loc": "Hyderabad, Bengaluru", "focus": "Largest R&D Site outside US; Medical Device Software, Surgical Robotics, Digital Health, IoT", "portal": "https://www.medtronic.com/in-en/about/careers.html"},
    {"company": "Boston Scientific", "gcc": "Boston Scientific R&D and Analytics Center", "loc": "Gurugram, Pune", "focus": "Minimally Invasive Medical Device Software, Product Analytics, Regulatory Data Governance", "portal": "https://jobs.bostonscientific.com/"},
    {"company": "Stryker", "gcc": "Stryker Global Technology Center (SGTC)", "loc": "Gurugram, Bengaluru", "focus": "Surgical Robotics (Mako), Orthopedic Design, Digital Innovation & Product Security", "portal": "https://careers.stryker.com"},
    {"company": "Smith+Nephew", "gcc": "Smith+Nephew Global Technology & R&D Hub", "loc": "Pune", "focus": "Orthopedic & Sports Medicine Software, AI Surgical Robotics, Connected Wound Management", "portal": "https://www.smith-nephew.com/en/careers"},
    {"company": "GE HealthCare", "gcc": "GE HealthCare Global Tech & Medical Imaging R&D", "loc": "Bengaluru, Pune", "focus": "AI Medical Imaging, Edison Platform, Ultrasound/CT/MRI Data Engineering, Digital Hospital Solutions", "portal": "https://jobs.gehealthcare.com"},
    {"company": "Philips Healthcare", "gcc": "Philips Healthcare Innovation Center (HIC)", "loc": "Bengaluru, Pune", "focus": "Diagnostic Imaging, Connected Care, Precision Diagnostics AI, Medical Device Software", "portal": "https://www.careers.philips.com"},
    {"company": "Siemens Healthineers", "gcc": "Siemens Healthineers Technology Center", "loc": "Bengaluru, Chennai", "focus": "Medical AI & Digital Twin, CT/MR Software, Laboratory Automation Systems, Clinical Imaging", "portal": "https://www.siemens-healthineers.com/en-in/careers"},
    {"company": "Abbott", "gcc": "Abbott Diagnostics & Nutrition Science GCC", "loc": "Mumbai, Bengaluru", "focus": "Continuous Glucose Monitoring (FreeStyle Libre) Data Systems, Diagnostics R&D, Nutrition Analytics", "portal": "https://www.abbott.com/careers.html"},
    {"company": "Alcon", "gcc": "Alcon Ophthalmic R&D Global Capability Center", "loc": "Bengaluru", "focus": "Ophthalmic Surgical Instrumentation Software, AI Eye Care Diagnostics, Global PLM Architecture", "portal": "https://www.alcon.com/careers"},
    {"company": "BD (Becton Dickinson)", "gcc": "BD Technology Campus India", "loc": "Bengaluru, Gurugram", "focus": "MedTech Product Engineering, Automated Drug Dispensing, Flow Cytometry Software, Clinical Informatics", "portal": "https://jobs.bd.com/"},
    {"company": "Edwards Lifesciences", "gcc": "Edwards IT Innovation Hub", "loc": "Pune", "focus": "Heart Valve Therapy Digital Solutions, Critical Care Monitoring Cloud, Enterprise Data Engineering", "portal": "https://www.edwards.com/careers"},
    {"company": "Intuitive Surgical", "gcc": "Intuitive Surgical GCC India", "loc": "Bengaluru", "focus": "da Vinci Surgical System Software Quality, Post-Market Surveillance Analytics, Robotic Telemetry Data", "portal": "https://careers.intuitive.com"},
    {"company": "Danaher (Cepheid / Beckman / Leica)", "gcc": "Danaher India Technology Centers", "loc": "Bengaluru, Pune", "focus": "Molecular Diagnostics Software (GeneXpert), Life Science Instrumentation, Automation Platforms", "portal": "https://jobs.danaher.com"},
    {"company": "Zimmer Biomet", "gcc": "Zimmer Biomet Medical Robotics & Tech Hub", "loc": "Gurugram, Noida", "focus": "ROSA Robotics Platform, Orthopedic Surgical Intelligence, Patient Sensor Analytics", "portal": "https://www.zimmerbiomet.com/en/about-us/careers.html"},
    {"company": "Baxter Healthcare", "gcc": "Baxter Global Delivery Center & R&D Center", "loc": "Bengaluru, Gurugram", "focus": "Renal Care Technology, Infusion Systems Software, Digital Health Data Infrastructure", "portal": "https://jobs.baxter.com/"},
    {"company": "Terumo", "gcc": "Terumo Global Technology Center", "loc": "Hyderabad", "focus": "Cardiovascular & Blood Management Technology, Interventional Medical Systems", "portal": "https://www.terumo.com/careers"},
    {"company": "Olympus Medical Systems", "gcc": "Olympus Medical Systems Tech Hub", "loc": "Gurugram", "focus": "Endoscopy Diagnostic AI, Surgical Visualization Software, Healthcare Operations IT", "portal": "https://www.olympus-global.com/careers/"},
    {"company": "Fresenius Medical Care", "gcc": "Fresenius Kidney Care Tech Hub", "loc": "Bengaluru, Chennai", "focus": "Dialysis Machine Telemetry, Renal Data Management, Connected Health Platforms", "portal": "https://www.freseniusmedicalcare.com/en/careers"},
    {"company": "ResMed", "gcc": "ResMed Digital Health & Data Analytics Hub", "loc": "Bengaluru", "focus": "Sleep Apnea & Respiratory Cloud Platforms, Connected Care Patient Analytics", "portal": "https://careers.resmed.com"},
    {"company": "Dexcom", "gcc": "Dexcom CGM Technology Center", "loc": "Bengaluru", "focus": "Continuous Glucose Monitoring Cloud Architecture, Real-Time Sensor Data Ingestion", "portal": "https://careers.dexcom.com"},
    {"company": "Insulet Corporation", "gcc": "Insulet Diabetes Tech Software Hub", "loc": "Bengaluru", "focus": "Omnipod Automated Insulin Delivery Systems, Mobile Health Apps, Clinical IoT", "portal": "https://www.insulet.com/careers"},

    # Life Sciences Instrumentation & Analytical Tools
    {"company": "Thermo Fisher Scientific", "gcc": "Thermo Fisher R&D Centre of Excellence & IT Hub", "loc": "Bengaluru, Hyderabad", "focus": "Chromatography/Spectrometry Software, Laboratory Information Management (LIMS), Bioproduction", "portal": "https://jobs.thermofisher.com"},
    {"company": "Agilent Technologies", "gcc": "Agilent Life Sciences & Chemical Analysis CoE", "loc": "Manesar/NCR, Bengaluru, Mumbai", "focus": "Analytical Chemistry Software, Genomics Solutions, Lab Automation Informatics", "portal": "https://careers.agilent.com"},
    {"company": "Waters Corporation", "gcc": "Waters Global Capability Center", "loc": "Bengaluru", "focus": "Liquid Chromatography & Mass Spectrometry Software, Empower CDS Cloud, Analytical Data Science", "portal": "https://www.waters.com/waters/en_US/Careers/nav.htm?cid=1000003"},
    {"company": "Revvity (PerkinElmer)", "gcc": "Revvity Omics & Health Sciences CoE", "loc": "Chennai, Mumbai", "focus": "Genomic Diagnostics, Drug Discovery Imaging, Newborn Screening Informatics", "portal": "https://www.revvity.com/careers"},
    {"company": "Illumina", "gcc": "Illumina Genomics Data & Solutions Hub", "loc": "Bengaluru", "focus": "Next-Generation Sequencing (NGS) Informatics, Genomic Big Data Pipelines, Variant Analysis", "portal": "https://www.illumina.com/company/careers.html"},
    {"company": "Bio-Rad Laboratories", "gcc": "Bio-Rad Clinical Diagnostics Analytics Hub", "loc": "Chennai, Mumbai", "focus": "Life Science Research Systems, Clinical Diagnostics Quality Control Data", "portal": "https://www.bio-rad.com/en-in/corporate/careers"},

    # Top Contract Research Organizations (CROs) & CDMOs
    {"company": "IQVIA", "gcc": "IQVIA India Commercial Analytics, RWE & Data Science Hub", "loc": "Bengaluru, Kochi, Mumbai, Gurugram", "focus": "Real-World Evidence (RWE), Commercial Pharma Consulting, Clinical Data Management, Omnichannel Analytics", "portal": "https://jobs.iqvia.com"},
    {"company": "Parexel", "gcc": "Parexel International Global Capability Center", "loc": "Hyderabad, Bengaluru, Chandigarh", "focus": "Global Clinical Operations, Biostatistics, AI-assisted Pharmacovigilance, Regulatory Strategy", "portal": "https://jobs.parexel.com"},
    {"company": "ICON plc", "gcc": "ICON Clinical Research & Data Systems", "loc": "Chennai, Bengaluru, Trivandrum", "focus": "End-to-End Clinical Trial Operations, Medical Writing, Health Economics & Outcomes Research (HEOR)", "portal": "https://careers.iconplc.com"},
    {"company": "Syneos Health", "gcc": "Syneos Global Life Sciences & Technology Centre", "loc": "Hyderabad, Gurugram", "focus": "Biopharmaceutical Clinical Development, Commercial Field Solutions, Omnichannel Patient Strategy", "portal": "https://www.syneoshealth.com/careers"},
    {"company": "Medpace", "gcc": "Medpace Clinical Data & Biostatistics Hub", "loc": "Navi Mumbai", "focus": "Full-Service Clinical Trial Execution, Biostatistics, Clinical Data Management, Regulatory Affairs", "portal": "https://careers.medpace.com"},
    {"company": "Labcorp (Covance)", "gcc": "Labcorp Drug Development & Clinical Operations", "loc": "Bengaluru, Chennai", "focus": "Central Laboratory Operations, Clinical Biomarker Analysis, Nonclinical Development Data", "portal": "https://careers.labcorp.com"},
    {"company": "Charles River Laboratories", "gcc": "Charles River Preclinical Data Services", "loc": "Bengaluru", "focus": "Early-Stage Drug Discovery Analytics, Safety Assessment Informatics, Microbial Solutions", "portal": "https://jobs.criver.com"},
    {"company": "Syngene International", "gcc": "Syngene Contract Research & Data Science Hub", "loc": "Bengaluru, Hyderabad", "focus": "Discovery Chemistry, Biologics Characterization, Bioinformatics, Clinical Trial Testing", "portal": "https://www.syngeneintl.com/careers/"},
    {"company": "Aragen Life Sciences", "gcc": "Aragen Preclinical & Small Molecule Analytics Hub", "loc": "Hyderabad, Bengaluru", "focus": "Small Molecule & Biologics Discovery, Formulation Development, Analytical R&D", "portal": "https://www.aragen.com/careers/"},
    {"company": "Piramal Pharma Solutions", "gcc": "Piramal Discovery Solutions & Analytics Hub", "loc": "Mumbai, Ahmedabad", "focus": "Contract Development & Manufacturing, High Potent API Data Systems, Commercial Release", "portal": "https://www.piramalpharmasolutions.com/careers"},

    # Top Health Plans, Payer Analytics & Commercial Tech
    {"company": "UnitedHealth Group (Optum)", "gcc": "Optum Global Solutions (India)", "loc": "Gurugram, Noida, Bengaluru, Hyderabad", "focus": "Largest Healthcare Analytics GCC in India; Claims Adjudication, Healthcare Big Data, Care Delivery, Clinical AI", "portal": "https://careers.unitedhealthgroup.com"},
    {"company": "Carelon Global Solutions (Elevance Health)", "gcc": "Carelon Healthcare Innovation Hubs", "loc": "Gurugram, Bengaluru, Hyderabad", "focus": "Health Plan Operations, Digital Claims Transformation, Healthcare AI & Automation, Provider Analytics", "portal": "https://carelonglobal.in/careers"},
    {"company": "Evernorth Health Services (The Cigna Group)", "gcc": "Evernorth Innovation Hub", "loc": "Hyderabad, Bengaluru", "focus": "Pharmacy Benefits Management (Express Scripts), Data Science & Generative AI, Care Solutions", "portal": "https://www.evernorth.com/careers"},
    {"company": "Cardinal Health", "gcc": "Cardinal Health International India (CHII)", "loc": "Bengaluru", "focus": "Augmented Intelligence in Healthcare Logistics, Pharmaceutical Distribution Systems, Enterprise Analytics", "portal": "https://www.cardinalhealth.com/en/about-us/careers.html"},
    {"company": "Cencora (AmerisourceBergen)", "gcc": "Cencora Global Healthcare Solutions Hub", "loc": "Pune, Hyderabad", "focus": "Pharmaceutical Sourcing Analytics, Specialty Distribution IT, Commercial Solutions Infrastructure", "portal": "https://www.cencora.com/careers"},
    {"company": "McKesson", "gcc": "McKesson Technology Solutions India", "loc": "Bengaluru, Hyderabad", "focus": "Healthcare Supply Chain Big Data, Oncology Practice Management Software, Pharmacy Tech", "portal": "https://careers.mckesson.com"},
    {"company": "Centene Corporation", "gcc": "Centene Healthcare Data Analytics & Claims Hub", "loc": "Hyderabad", "focus": "Government-Sponsored Healthcare Analytics, Medicaid/Medicare Claims Intelligence, Population Health", "portal": "https://jobs.centene.com"},
    {"company": "Humana", "gcc": "Humana Healthcare Analytics & Digital Hub", "loc": "Bengaluru", "focus": "Senior Healthcare Analytics, Medicare Advantage Data Engineering, Predictive Clinical Models", "portal": "https://careers.humana.com"},
    {"company": "Cohere Health", "gcc": "Cohere Health Intelligent Prior Authorization Hub", "loc": "Hyderabad (Remote entity)", "focus": "AI Clinical Prior Authorization, Value-Based Care Analytics, Interoperability FHIR Pipelines", "portal": "https://job-boards.greenhouse.io/coherehealth"},
    {"company": "Axtria", "gcc": "Axtria Life Sciences Commercial Tech Hub", "loc": "Noida, Gurugram, Bengaluru", "focus": "Cloud-based Pharma Commercial Analytics, Marketing Mix (MMx), Incentive Compensation, DataMax/SalesIQ", "portal": "https://www.axtria.com/careers"},
    {"company": "ZS Associates", "gcc": "ZS Associates Healthcare Commercial Strategy & Analytics", "loc": "Gurugram, Noida, Pune, Bengaluru", "focus": "Global Leader in Pharma Commercial Strategy, Sales Force Effectiveness, HCP/HCO Data Governance, Big Data Pipelines", "portal": "https://www.zs.com/careers"},
    {"company": "PharmSight", "gcc": "PharmSight Biopharma Commercial Analytics Hub", "loc": "Noida, Gurugram", "focus": "Biopharma Demand Forecasting, Patient Flow Analytics, Competitive Intelligence Modeling", "portal": "https://pharmsight.com/careers"},
    {"company": "Precision AQ (Precision Medicine Group)", "gcc": "Precision AQ Healthcare Data Products Hub", "loc": "Bengaluru (Remote entity)", "focus": "DecodeRx Healthcare Intelligence, Payer Analytics, Formulary Access Data, Evidence Solutions", "portal": "https://job-boards.greenhouse.io/precisionmedicinegroup"},
    {"company": "Elsevier (RELX Health)", "gcc": "Elsevier Health Sciences & Medical Analytics Hub", "loc": "Bengaluru, Chennai", "focus": "ClinicalKey Knowledge Graphs, Medical Data Architecture, Clinical AI Decision Support", "portal": "https://relx.wd3.myworkdayjobs.com/ElsevierJobs"},

    # Top Indian Global Biopharma Leaders with Advanced Tech/Analytics Footprint
    {"company": "Sun Pharma", "gcc": "Sun Pharma Global Analytics & Digital Tech Hub", "loc": "Mumbai, Gurugram", "focus": "Global Formulation Data Systems, Commercial Strategy, Supply Chain Visibility, Biosimilars", "portal": "https://sunpharma.com/careers/"},
    {"company": "Dr. Reddy's Laboratories", "gcc": "Dr. Reddy's Biologics & Digital Transformation Hub", "loc": "Hyderabad", "focus": "AI in Process Chemistry, Commercial Analytics, Global Supply Chain Orchestration, Biologics IT", "portal": "https://careers.drreddys.com"},
    {"company": "Cipla", "gcc": "Cipla Digital Health & Commercial Analytics Hub", "loc": "Mumbai, Bengaluru", "focus": "Respiratory Commercial Analytics, Smart Manufacturing IoT, Global Regulatory Data Management", "portal": "https://www.cipla.com/careers"},
    {"company": "Biocon & Biocon Biologics", "gcc": "Biocon Digital R&D & Commercial Data Systems", "loc": "Bengaluru", "focus": "Biosimilars Commercialization Analytics, Clinical Trial IT, Quality Control Data Pipelines", "portal": "https://www.biocon.com/careers/"},
    {"company": "Lupin Pharmaceuticals", "gcc": "Lupin Global Digital & Commercial Analytics Hub", "loc": "Mumbai, Pune", "focus": "Digital Therapeutics, Generics & Specialty Commercial Analytics, Global Shared Services", "portal": "https://www.lupin.com/careers/"},
    {"company": "Zydus Lifesciences", "gcc": "Zydus Healthcare Analytics & Formulation Data Hub", "loc": "Ahmedabad, Mumbai", "focus": "NCE Drug Discovery Informatics, Commercial Market Dynamics, Vaccine Supply Chain", "portal": "https://zyduslife.com/careers"},
    {"company": "Alkem Laboratories", "gcc": "Alkem Commercial & Clinical Analytics Hub", "loc": "Mumbai", "focus": "Commercial Brand Analytics, Field Force Effectiveness, Digital Supply Chain", "portal": "https://www.alkemlabs.com/careers"},
    {"company": "Torrent Pharmaceuticals", "gcc": "Torrent Digital Commercial Analytics Hub", "loc": "Ahmedabad", "focus": "Cardiology & CNS Commercial BI, Prescription Data Modeling, Manufacturing Analytics", "portal": "https://www.torrentpharma.com/careers"},
    {"company": "Divi's Laboratories", "gcc": "Divi's Active Pharmaceutical Ingredients Digital Hub", "loc": "Hyderabad", "focus": "Custom API Synthesis Informatics, Quality Analytics, Global Export Tracking", "portal": "https://www.divislabs.com/careers/"},
    {"company": "Aurobindo Pharma", "gcc": "Aurobindo Formulations & Global Regulatory Data Hub", "loc": "Hyderabad", "focus": "Global Regulatory Filing Systems, Formulation Analytics, Supply Chain IT", "portal": "https://www.aurobindo.com/careers/"},
    {"company": "Mankind Pharma", "gcc": "Mankind Digital Health & Commercial BI Hub", "loc": "New Delhi, Gurugram", "focus": "Domestic Formulation Analytics, Supply Chain Network Optimization, Digital Marketing BI", "portal": "https://www.mankindpharma.com/careers"},
    {"company": "Intas Pharmaceuticals", "gcc": "Intas Biopharmaceuticals Digital Operations", "loc": "Ahmedabad", "focus": "Plasma & Biologics Data Systems, European Regulatory Analytics, Clinical Compliance", "portal": "https://www.intaspharma.com/careers/"},
    {"company": "Glenmark Pharmaceuticals", "gcc": "Glenmark Commercial Analytics & Innovation Hub", "loc": "Mumbai", "focus": "Dermatology & Respiratory Commercial Strategy, Clinical Data Pipelines, Ichnos Biologics", "portal": "https://www.glenmarkpharma.com/careers"},
    {"company": "Gland Pharma", "gcc": "Gland Injectables Quality & Data Engineering Hub", "loc": "Hyderabad", "focus": "Injectable Manufacturing Analytics, Global Quality Assurance Systems, Regulatory Traceability", "portal": "https://www.glandpharma.com/careers.html"},
]

# ── TOP ADJACENT DOMAIN COMPANIES (CONSULTING, AI, DATA PLATFORMS, FINTECH, E-COM) ──
ADJACENT_COMPANIES_HUBS = [
    # 1. HealthTech & Healthcare Data Platforms (Tier 1 Fit)
    {"company": "Innovaccer", "gcc": "Innovaccer Health Data Cloud R&D Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Healthcare Data Unification & Clinical AI Platforms", "loc": "Noida, Bengaluru", "focus": "Healthcare Big Data Platform, Patient Record Unification, Value-Based Care Analytics", "portal": "https://innovaccer.com/careers"},
    {"company": "CitiusTech", "gcc": "CitiusTech Healthcare Digital Engineering Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Healthcare Technology & Interoperability Engineering", "loc": "Mumbai, Pune, Gurugram, Bengaluru, Hyderabad", "focus": "Clinical Decision Support, FHIR/HL7 Data Engineering, Healthcare AI & Payer Systems", "portal": "https://www.citiustech.com/careers"},
    {"company": "Indegene", "gcc": "Indegene Life Sciences Commercial Tech Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "AI-Native Biopharma Commercialization Platforms", "loc": "Bengaluru", "focus": "Commercialization Tech, Omnichannel Pharma Marketing BI, Regulatory Automation", "portal": "https://www.indegene.com/careers"},
    {"company": "Athenahealth", "gcc": "Athenahealth India Tech & Product Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Cloud EHR & Healthcare Practice Intelligence", "loc": "Bengaluru, Chennai, Pune", "focus": "Cloud-based Healthcare Software, Revenue Cycle Analytics, Clinical EHR Pipelines", "portal": "https://www.athenahealth.com/careers"},
    {"company": "Veeva Systems", "gcc": "Veeva Systems Life Sciences Cloud Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Life Sciences Cloud & Commercial CRM Architecture", "loc": "Bengaluru, Hyderabad", "focus": "Veeva Vault, Commercial CRM Data Architecture, Clinical Data Cloud", "portal": "https://www.veeva.com/careers/"},
    {"company": "Flatiron Health", "gcc": "Flatiron Health Oncology Data Systems", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Real-World Oncology Data & Clinical Intelligence", "loc": "Bengaluru (Remote entity)", "focus": "Real-World Oncology Evidence, Cancer Clinical Trial Informatics, EHR Data Modeling", "portal": "https://flatiron.com/careers/"},
    {"company": "Clarivate", "gcc": "Clarivate Life Sciences & Healthcare Analytics Hub", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "Biopharma Market Intelligence & DRG Analytics", "loc": "Noida, Bengaluru, Hyderabad", "focus": "Decision Resources Group (DRG) Analytics, BioWorld Clinical Intelligence, IP Data", "portal": "https://clarivate.com/careers/"},
    {"company": "Eversana", "gcc": "Eversana Global Life Sciences Commercial Services", "domain": "Healthcare, Pharma, MedTech & Life Sciences", "sub": "End-to-End Pharma Commercialization & Pricing BI", "loc": "Pune, Gurugram", "focus": "Pharma Commercial Deployment, Patient Support Data, Global Pricing Analytics", "portal": "https://www.eversana.com/careers/"},

    # 2. Advanced Analytics & AI Consultancies (Tier 1 Fit)
    {"company": "Tiger Analytics", "gcc": "Tiger Analytics Advanced AI Consulting Hub", "domain": "Strategy & Technology Consulting", "sub": "Enterprise AI & Advanced Data Science Consulting", "loc": "Chennai, Bengaluru, Hyderabad", "focus": "Predictive ML Modeling, Data Engineering Pipelines, Cross-industry Decision Analytics", "portal": "https://www.tigeranalytics.com/careers/"},
    {"company": "Tredence", "gcc": "Tredence Analytics & AI CoE", "domain": "Strategy & Technology Consulting", "sub": "Last-Mile AI Adoption & Data Engineering Solutions", "loc": "Bengaluru, Gurugram", "focus": "Data Engineering, CPG/Healthcare Analytics Accelerators, Enterprise AI Deployment", "portal": "https://www.tredence.com/careers"},
    {"company": "Fractal Analytics", "gcc": "Fractal AI & Decision Intelligence Hub", "domain": "Strategy & Technology Consulting", "sub": "Decision Sciences, Healthcare AI & Enterprise Data Architecture", "loc": "Mumbai, Bengaluru, Gurugram, Pune", "focus": "Senseforth Conversational AI, Qure.ai Healthcare Imaging, Enterprise Decision Systems", "portal": "https://fractal.ai/careers/"},
    {"company": "LatentView Analytics", "gcc": "LatentView Data Engineering & Consulting Hub", "domain": "Strategy & Technology Consulting", "sub": "Digital Analytics, Data Governance & Business Intelligence", "loc": "Chennai, Bengaluru, Gurugram", "focus": "Data Lake Architecture, Supply Chain BI, Marketing Analytics & Data Governance", "portal": "https://www.latentview.com/careers/"},
    {"company": "TheMathCompany (MathCo)", "gcc": "MathCo Enterprise AI & Analytics CoE", "domain": "Strategy & Technology Consulting", "sub": "Custom Enterprise AI & Data Strategy Advisory", "loc": "Bengaluru", "focus": "Co.dx AI Platform, Data Science Consulting, Large-Scale Analytics Modernization", "portal": "https://mathco.com/careers/"},
    {"company": "Quantiphi", "gcc": "Quantiphi Applied AI & Big Data Solutions", "domain": "Strategy & Technology Consulting", "sub": "Applied AI, LLM Systems & Cloud Data Engineering", "loc": "Mumbai, Bengaluru", "focus": "Custom Generative AI Agents, Cloud Data Lakehouses, HealthCare & BFSI AI Engineering", "portal": "https://quantiphi.com/careers/"},

    # 3. Cloud Data Lakehouse, Databases & Infrastructure Platforms (Tier 1 Fit)
    {"company": "Snowflake", "gcc": "Snowflake India Engineering & Tech Center", "domain": "AI Systems & Data Engineering", "sub": "Cloud Data Lakehouse & AI Systems Engineering", "loc": "Pune, Bengaluru", "focus": "Data Cloud Architecture, Snowpark, High-Performance Transactional & Analytical SQL", "portal": "https://www.snowflake.com/en/company/careers/"},
    {"company": "Databricks", "gcc": "Databricks India Engineering Hub", "domain": "AI Systems & Data Engineering", "sub": "Unified Analytics, Apache Spark & Lakehouse Platform", "loc": "Bengaluru", "focus": "Apache Spark Engine, Delta Lake, MLflow, AI Agents & Big Data Orchestration", "portal": "https://www.databricks.com/company/careers"},
    {"company": "Confluent", "gcc": "Confluent India Streaming Data Engineering Hub", "domain": "AI Systems & Data Engineering", "sub": "Event-Driven Architecture & Real-Time Apache Kafka Data", "loc": "Bengaluru", "focus": "Real-Time Data Streaming, Kafka Pipelines, Flink SQL Data Processing", "portal": "https://www.confluent.io/careers/"},
    {"company": "MongoDB", "gcc": "MongoDB India Software Engineering & Analytics Hub", "domain": "AI Systems & Data Engineering", "sub": "Distributed Document Databases & Vector Search", "loc": "Bengaluru, Gurugram, Pune", "focus": "Distributed Systems, Vector Search AI, Atlas Cloud Database Infrastructure", "portal": "https://www.mongodb.com/careers"},
    {"company": "Elastic", "gcc": "Elasticsearch India Distributed Systems Hub", "domain": "AI Systems & Data Engineering", "sub": "Search & Observability Big Data Infrastructure", "loc": "Bengaluru, Pune, Remote", "focus": "Elasticsearch, Logstash, Kibana Data Pipelines, Enterprise Observability Systems", "portal": "https://www.elastic.co/about/careers"},
    {"company": "Fivetran", "gcc": "Fivetran India Automated Data Ingestion CoE", "domain": "AI Systems & Data Engineering", "sub": "Automated ELT Pipelines & Cloud Ingestion Connectors", "loc": "Bengaluru", "focus": "Automated ETL/ELT Connectors, Data Warehouse Sync, Change Data Capture (CDC)", "portal": "https://fivetran.com/careers"},
    {"company": "Dremio", "gcc": "Dremio Data Lakehouse Platform Hub", "domain": "AI Systems & Data Engineering", "sub": "SQL Lakehouse Engine & Apache Arrow Query Acceleration", "loc": "Hyderabad, Bengaluru", "focus": "SQL Lakehouse Query Engine, Apache Iceberg Data Management, Sub-second Analytics", "portal": "https://www.dremio.com/careers/"},
    {"company": "Cloudera", "gcc": "Cloudera Enterprise Big Data Hub", "domain": "AI Systems & Data Engineering", "sub": "Enterprise Hadoop, Spark & Hybrid Cloud Data Platforms", "loc": "Bengaluru", "focus": "Enterprise Data Platform, Apache Spark, Hive, Data Governance & Observability", "portal": "https://www.cloudera.com/about/careers.html"},

    # 4. E-Commerce Logistics, D2C, Marketplaces & AdTech (Tier 2 Fit)
    {"company": "Flipkart", "gcc": "Flipkart Commerce & Logistics Tech Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Omnichannel Marketplace, Supply Chain & AdTech BI", "loc": "Bengaluru", "focus": "Ekart Supply Chain Tech, Multi-Store SKU Inventory Sync, Search & Ads Data Platform", "portal": "https://www.flipkartcareers.com"},
    {"company": "Swiggy", "gcc": "Swiggy Hyperlocal Logistics & Food Tech Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Quick Commerce (Instamart) Logistics & Real-Time Dispatch", "loc": "Bengaluru", "focus": "Last-Mile Delivery Routing, Dynamic Demand Modeling, Real-time Transaction Analytics", "portal": "https://careers.swiggy.com"},
    {"company": "Zomato", "gcc": "Zomato & Blinkit Quick Commerce Tech Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Quick Commerce & Hyperlocal Demand Analytics", "loc": "Gurugram", "focus": "Blinkit Dark Store Inventory Optimization, Supply Chain Reconciliation, User BI", "portal": "https://www.zomato.com/careers"},
    {"company": "Zepto", "gcc": "Zepto Quick Commerce Engineering Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "10-Minute Dark Store Supply Chain & Demand Forecasting", "loc": "Bengaluru, Mumbai", "focus": "Predictive Restock Modeling, Dark Store SKU Allocation, Real-Time Rider Telemetry", "portal": "https://www.zepto.co/careers"},
    {"company": "Delhivery", "gcc": "Delhivery Logistics Automation & Data Systems Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Autonomous Logistics Reconciliation & Transit Intelligence", "loc": "Gurugram, Bengaluru", "focus": "AWB Tracking Pipelines, Automated Freight Audit & Weight Reconciliation, Network Design", "portal": "https://www.delhivery.com/careers/"},
    {"company": "Shiprocket", "gcc": "Shiprocket D2C Logistics & Shipping Tech Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "D2C Courier Orchestration & Multi-Carrier Shipping APIs", "loc": "Gurugram, Bengaluru", "focus": "Multi-Carrier Shipping APIs, Courier Reconciliation, NDR/RTO Prediction Engines", "portal": "https://www.shiprocket.in/careers/"},
    {"company": "Lenskart", "gcc": "Lenskart Omnichannel Retail Tech CoE", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Omnichannel Eyewear Manufacturing & Retail Analytics", "loc": "Faridabad/Delhi NCR, Gurugram, Bengaluru", "focus": "Automated Warehouse Tech, Multi-Store Retail Sync, Customer Lifetime Value BI", "portal": "https://lenskart.openings.co/"},
    {"company": "InMobi", "gcc": "InMobi Global AdTech & Consumer Intelligence Hub", "domain": "E-Commerce, D2C & Retail Tech", "sub": "Programmatic Advertising, Mobile Attribution & Glance Platform", "loc": "Bengaluru, Delhi NCR", "focus": "High-throughput Bidstream Data Pipelines, Ad Targeting Optimization, Glance Content AI", "portal": "https://www.inmobi.com/company/careers/"},

    # 5. High-Frequency & Quant Trading, WealthTech & BFSI (Tier 2 Fit)
    {"company": "Tower Research Capital", "gcc": "Tower Research Capital India Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "High-Frequency Quantitative Trading & Low-Latency Data", "loc": "Gurugram, GIFT City", "focus": "Low-Latency Market Data Processing, Algorithmic Trading Systems, Quantitative Financial Research", "portal": "https://www.tower-research.com/open-positions"},
    {"company": "WorldQuant", "gcc": "WorldQuant Quantitative Research & Predictive Modeling", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Quantitative Alpha Research & Systematic Investing", "loc": "Gurugram (Aerocity), Bengaluru, Mumbai", "focus": "Quantitative Financial Modeling, Global Market Alpha Generation, Predictive Time-Series Data", "portal": "https://www.worldquant.com/careers/"},
    {"company": "Jump Trading", "gcc": "Jump Trading Quantitative Trading Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Proprietary Quantitative Trading & Market Making", "loc": "GIFT City, Mumbai", "focus": "Algorithmic Market Making, High-Throughput Exchange Data Pipelines, Statistical Modeling", "portal": "https://www.jumptrading.com/careers/"},
    {"company": "Graviton Research Capital", "gcc": "Graviton Research Capital India Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "High-Frequency Quantitative Trading & Market Making", "loc": "Gurugram, Mumbai", "focus": "High-Frequency Trading Algorithms, Ultra-Low Latency Infrastructure, Mathematical Finance", "portal": "https://gravitontrading.com/careers"},
    {"company": "Quadeye", "gcc": "Quadeye Quantitative Trading Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Quantitative Trading, Derivative Analytics & Risk Modeling", "loc": "Gurugram", "focus": "Quantitative Derivative Modeling, Algorithmic Execution, High-Performance Transaction Processing", "portal": "https://quadeye.com/careers/"},
    {"company": "Razorpay", "gcc": "Razorpay Payment & Fintech Infrastructure Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Digital Payments Gateway, Neobanking & Risk Systems", "loc": "Bengaluru", "focus": "Payment Gateway Infrastructure, Fraud Detection ML Pipelines, High-Volume Financial Ledgers", "portal": "https://razorpay.com/jobs/"},
    {"company": "CRED", "gcc": "CRED High-Trust Financial Products Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Premium Financial Rewards & Credit Intelligence", "loc": "Bengaluru", "focus": "Credit Score Modeling, Payment Orchestration, Behavioral Cohort Analytics", "portal": "https://careers.cred.club/"},
    {"company": "Groww", "gcc": "Groww WealthTech & Investment Systems Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Retail Investment, Stock Trading & Mutual Funds Platform", "loc": "Bengaluru", "focus": "High-Concurrency Order Processing, Real-Time Market Feed Ingestion, User Financial BI", "portal": "https://groww.in/careers"},
    {"company": "Zerodha", "gcc": "Zerodha Tech & Kite Trading Platform Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "Discount Brokerage, Kite API & Financial Systems", "loc": "Bengaluru", "focus": "Ultra-Efficient Backend Architecture, Kite Trading APIs, High-Concurrency Financial Systems", "portal": "https://zerodha.com/careers"},
    {"company": "Policybazaar (PB Fintech)", "gcc": "Policybazaar InsurTech & Insurance Data Hub", "domain": "Fintech, BFSI & Quantitative Trading", "sub": "InsurTech Aggregation & Risk Underwriting Analytics", "loc": "Gurugram", "focus": "Insurance Comparison Engines, Underwriting Risk Models, Customer Conversion Pipelines", "portal": "https://www.policybazaar.com/careers/"},

    # 6. Enterprise SaaS, Developer Tools & Workflow Automation (Tier 2 Fit)
    {"company": "Postman", "gcc": "Postman API Platform Engineering Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "API Collaboration & Developer Platform Infrastructure", "loc": "Bengaluru", "focus": "API Lifecycle Management, Automated API Testing, Distributed Cloud Architecture", "portal": "https://www.postman.com/careers/"},
    {"company": "BrowserStack", "gcc": "BrowserStack Cloud Testing Infrastructure Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Software Testing Cloud & Browser Infrastructure", "loc": "Mumbai, Bengaluru", "focus": "Global Cloud Testing Grid, Real-Device Cloud Infrastructure, Telemetry Data Engineering", "portal": "https://www.browserstack.com/careers"},
    {"company": "Hasura", "gcc": "Hasura GraphQL & Data Engine Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "GraphQL Data APIs & Instant Backend Engine", "loc": "Bengaluru, Remote", "focus": "GraphQL Data Connectors, Sub-Second SQL Compilation, Real-Time Subscriptions", "portal": "https://hasura.io/careers/"},
    {"company": "Chargebee", "gcc": "Chargebee Subscription Billing & Revenue Intelligence", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Subscription Management & Recurring Billing SaaS", "loc": "Chennai, Bengaluru", "focus": "Recurring Billing Ledgers, Revenue Recognition Analytics, Payment Gateway Integrations", "portal": "https://www.chargebee.com/careers/"},
    {"company": "Darwinbox", "gcc": "Darwinbox Enterprise HRTech & People Analytics Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Enterprise Human Capital Management & People BI", "loc": "Hyderabad, Bengaluru, Delhi NCR", "focus": "Enterprise HCM Workflows, Employee Lifecycle Analytics, Global Payroll Data Engine", "portal": "https://darwinbox.com/careers"},
    {"company": "LeadSquared", "gcc": "LeadSquared Sales Execution & Marketing Automation", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Sales Execution CRM & Workflow Automation", "loc": "Bengaluru, Noida", "focus": "High-Volume Lead Ingestion, Real-Time Field Force Routing, Marketing Attribution BI", "portal": "https://www.leadsquared.com/careers/"},
    {"company": "Whatfix", "gcc": "Whatfix Digital Adoption & User Analytics Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Digital Adoption Platform (DAP) & Product Analytics", "loc": "Bengaluru", "focus": "In-App Guidance Telemetry, Enterprise Software Adoption Metrics, Behavioral Modeling", "portal": "https://whatfix.com/careers/"},
    {"company": "Icertis", "gcc": "Icertis Contract Intelligence AI Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Contract Lifecycle Management (CLM) & AI Analytics", "loc": "Pune", "focus": "Contract Intelligence AI, Enterprise Legal Data Ingestion, Compliance Data Pipelines", "portal": "https://www.icertis.com/company/careers/"},
    {"company": "HighRadius", "gcc": "HighRadius Autonomous Finance Platform Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Autonomous Order-to-Cash & Treasury AI Platforms", "loc": "Hyderabad, Bhubaneswar", "focus": "Order-to-Cash Automation, AI-based Cash Forecasting, Invoice Reconciliation Engines", "portal": "https://www.highradius.com/careers/"},
    {"company": "Druva", "gcc": "Druva Cloud Data Protection & Cyber Resilience Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "SaaS-Based Cloud Data Protection & Observability", "loc": "Pune", "focus": "Cloud Backup & Disaster Recovery, Deduplication Engines, Global Data Compliance", "portal": "https://www.druva.com/about/careers/"},
    {"company": "Gainsight", "gcc": "Gainsight Customer Success & Product Analytics Hub", "domain": "Enterprise SaaS & Cloud Platforms", "sub": "Customer Success & Product Experience SaaS", "loc": "Hyderabad", "focus": "Customer Health Score Modeling, Churn Prediction Data Pipelines, SaaS Usage Telemetry", "portal": "https://www.gainsight.com/company/careers/"},
]


def load_baseline_records() -> dict[str, dict]:
    """Load baseline records from master_companies_mdm.csv."""
    records: dict[str, dict] = {}
    if not BASELINE_CSV.exists():
        return records

    with open(BASELINE_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            comp = r["company_name"].strip()
            records[comp] = r
    return records


def get_persona_rationale_for_domain(domain: str, comp_name: str) -> tuple[str, str, int]:
    """Assigns custom persona match rationale, target roles & fit rating."""
    if domain == "Healthcare, Pharma, MedTech & Life Sciences":
        return (
            "Highest tier fit (96-98%). Direct match for 3+ years at ZS Associates managing HCP/HCO patient & sales data pipelines, "
            "HIPAA de-identification/data stripping, 15+ Apache Airflow pipelines, Snowflake data lakes, and commercial analytics forecasting.",
            "Data Engineer | Analytics Engineer | Commercial Analytics Consultant | Biopharma Data Analyst | HealthTech BI Lead",
            98
        )
    elif domain == "Strategy & Technology Consulting":
        return (
            "Direct match for 3.2 yrs ZS Associates business tech consulting background + Rush by Kira client consulting. "
            "Expertise in scoping client analytics, translating business problems into high-performance SQL/data architectures, and multi-stakeholder delivery.",
            "Business Technology Consultant | Solutions Architect | Senior Analytics Consultant | Analytics Advisory Lead",
            95
        )
    elif domain == "AI Systems & Data Engineering":
        return (
            "Core technical fit (94-96%). Strong PySpark, SQL performance tuning, Snowflake, Trino, PostgreSQL, Apache Airflow ETL, "
            "and autonomous AI agent development (webhook orchestrators, data reconciliation bots).",
            "Data Engineer | Analytics Engineer | AI Systems / Automation Engineer | Big Data Platform Engineer",
            94
        )
    elif domain == "E-Commerce, D2C & Retail Tech":
        return (
            "Strong functional fit (92-94%). Direct match for Rush by Kira consulting experience: autonomous courier reconciliation pipelines "
            "(Shopify + iThinkLogistics), multi-store SKU sync, predictive restock modeling, and marketing conversion analytics.",
            "Data Engineer | E-commerce Analytics Lead | Logistics Reconciliation Engineer | BI Engineer",
            93
        )
    elif domain == "Fintech, BFSI & Quantitative Trading":
        return (
            "Solid analytical fit (91-93%). Aligns with TresVista financial valuation experience (DCF/Comps for TMT sector), "
            "BA (Hons) Business Economics degree from Delhi University, and high-throughput transactional SQL modeling.",
            "Quantitative Data Analyst | Financial Data Engineer | Valuation & BI Consultant | Risk Analytics Engineer",
            91
        )
    elif domain == "Enterprise SaaS & Cloud Platforms":
        return (
            "Match for enterprise cloud data architectures, REST API integrations, event-driven webhooks, and product operations analytics.",
            "Analytics Engineer | Cloud Data Solutions Architect | Product Operations Analyst",
            90
        )
    else:
        return (
            "Applies core data engineering and pipeline optimization to enterprise manufacturing, supply chain, and global GCC engineering data flows.",
            "Data Analyst | Industrial Data Engineer | Systems Optimization Specialist",
            88
        )


def main():
    print("Loading baseline MDM records...")
    records = load_baseline_records()
    print(f"Loaded {len(records)} baseline records.")

    # 1. Merge Top 100 Pharma & MedTech GCCs
    print(f"Merging {len(TOP_100_PHARMA_MEDTECH_HUBS)} Pharma/MedTech India GCCs...")
    for item in TOP_100_PHARMA_MEDTECH_HUBS:
        c_name = item["company"]
        gcc_name = item["gcc"]
        loc = item["loc"]
        focus = item["focus"]
        portal = item["portal"]

        rationale, target_roles, fit_score = get_persona_rationale_for_domain("Healthcare, Pharma, MedTech & Life Sciences", c_name)
        desc = f"Global biopharmaceutical/MedTech leader operating a major India GCC dedicated to {focus}."

        if c_name in records:
            records[c_name]["gcc_india_hub"] = gcc_name
            records[c_name]["domain_pillar"] = "Healthcare, Pharma, MedTech & Life Sciences"
            records[c_name]["sub_domain"] = "Pharma Commercial Analytics / HealthTech & MedTech Engineering"
            records[c_name]["persona_match_rationale"] = rationale
            records[c_name]["recommended_target_roles"] = target_roles
            records[c_name]["candidate_fit_score"] = str(fit_score)
            records[c_name]["india_locations"] = loc
            records[c_name]["core_functional_focus"] = focus
            if not records[c_name].get("career_portal_url") or "google.com" in records[c_name].get("career_portal_url", ""):
                records[c_name]["career_portal_url"] = portal
            records[c_name]["company_overview"] = desc
        else:
            records[c_name] = {
                "company_name": c_name,
                "gcc_india_hub": gcc_name,
                "domain_pillar": "Healthcare, Pharma, MedTech & Life Sciences",
                "sub_domain": "Pharma Commercial Analytics / HealthTech & MedTech Engineering",
                "persona_match_rationale": rationale,
                "recommended_target_roles": target_roles,
                "candidate_fit_score": str(fit_score),
                "india_locations": loc,
                "core_functional_focus": focus,
                "compensation_benchmark": "Target Band: ₹20-28 LPA+",
                "network_contacts": "Direct Portal / Professional Network",
                "career_portal_url": portal,
                "company_overview": desc,
            }

    # 2. Merge Adjacent Domain Companies
    print(f"Merging {len(ADJACENT_COMPANIES_HUBS)} Adjacent Domain Companies...")
    for item in ADJACENT_COMPANIES_HUBS:
        c_name = item["company"]
        gcc_name = item["gcc"]
        domain = item["domain"]
        sub = item["sub"]
        loc = item["loc"]
        focus = item["focus"]
        portal = item["portal"]

        rationale, target_roles, fit_score = get_persona_rationale_for_domain(domain, c_name)
        desc = f"Industry leader in {sub} with major India engineering, data, and analytics hub focused on {focus}."

        if c_name in records:
            records[c_name]["gcc_india_hub"] = gcc_name
            records[c_name]["domain_pillar"] = domain
            records[c_name]["sub_domain"] = sub
            records[c_name]["persona_match_rationale"] = rationale
            records[c_name]["recommended_target_roles"] = target_roles
            records[c_name]["candidate_fit_score"] = str(fit_score)
            records[c_name]["india_locations"] = loc
            records[c_name]["core_functional_focus"] = focus
            if not records[c_name].get("career_portal_url") or "google.com" in records[c_name].get("career_portal_url", ""):
                records[c_name]["career_portal_url"] = portal
            records[c_name]["company_overview"] = desc
        else:
            records[c_name] = {
                "company_name": c_name,
                "gcc_india_hub": gcc_name,
                "domain_pillar": domain,
                "sub_domain": sub,
                "persona_match_rationale": rationale,
                "recommended_target_roles": target_roles,
                "candidate_fit_score": str(fit_score),
                "india_locations": loc,
                "core_functional_focus": focus,
                "compensation_benchmark": "Target Band: ₹20-28 LPA+",
                "network_contacts": "Direct Portal / Professional Network",
                "career_portal_url": portal,
                "company_overview": desc,
            }

    # Clean & Sort all records
    all_records = [records[k] for k in sorted(records.keys())]
    print(f"Total Unique Canonical Companies in MDM: {len(all_records)}")

    # ── Write master_companies_mdm.csv ───────────────────────────────────────
    csv_file = OUTPUT_DIR / "master_companies_mdm.csv"
    print(f"Writing {csv_file}...")
    fieldnames = [
        "company_name", "gcc_india_hub", "domain_pillar", "sub_domain",
        "persona_match_rationale", "recommended_target_roles", "candidate_fit_score",
        "india_locations", "core_functional_focus", "compensation_benchmark",
        "network_contacts", "career_portal_url", "company_overview"
    ]
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_records:
            writer.writerow(r)

    # ── Write master_companies_mdm.json ──────────────────────────────────────
    json_file = OUTPUT_DIR / "master_companies_mdm.json"
    print(f"Writing {json_file}...")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)

    # ── Separate by Pillars ──────────────────────────────────────────────────
    pharma_records = [r for r in all_records if r["domain_pillar"] == "Healthcare, Pharma, MedTech & Life Sciences"]
    consulting_records = [r for r in all_records if r["domain_pillar"] == "Strategy & Technology Consulting"]
    ai_records = [r for r in all_records if r["domain_pillar"] == "AI Systems & Data Engineering"]
    ecom_records = [r for r in all_records if r["domain_pillar"] == "E-Commerce, D2C & Retail Tech"]
    fintech_records = [r for r in all_records if r["domain_pillar"] == "Fintech, BFSI & Quantitative Trading"]
    saas_records = [r for r in all_records if r["domain_pillar"] == "Enterprise SaaS & Cloud Platforms"]
    industrial_records = [r for r in all_records if r["domain_pillar"] == "Industrial Tech, Conglomerates & Automotive"]

    # ── Write pharma_medtech_lifesciences.md ─────────────────────────────────
    pharma_md = OUTPUT_DIR / "pharma_medtech_lifesciences.md"
    print(f"Writing {pharma_md}...")
    with open(pharma_md, "w", encoding="utf-8") as f:
        f.write("# Healthcare, Pharma, MedTech & Life Sciences Master MDM Repository\n\n")
        f.write("**Candidate Target Alignment:** Tier 1 Highest Fit (98% Score)\n")
        candidate_name = os.getenv("CANDIDATE_NAME", "Candidate")
        candidate_yoe = os.getenv("CANDIDATE_TOTAL_YOE", "5")
        f.write(f"**Domain Background Match:** Direct alignment with {candidate_name}'s domain experience (HIPAA compliance, HCP/HCO claims data stripping, Snowflake ingestion layers, and Apache Airflow pipelines).\n\n")
        f.write(f"**Total Dedicated Companies in Repository:** {len(pharma_records)}\n\n")
        f.write("---\n\n")

        for idx, p in enumerate(pharma_records, start=1):
            f.write(f"### {idx}. {p['company_name']}\n")
            f.write(f"- **GCC / India Entity:** {p['gcc_india_hub']}\n")
            f.write(f"- **Sub-Domain:** {p['sub_domain']}\n")
            f.write(f"- **Locations in India:** {p['india_locations']}\n")
            f.write(f"- **Fit Score:** `{p['candidate_fit_score']}%` | **Target Roles:** `{p['recommended_target_roles']}`\n")
            f.write(f"- **Persona Match Rationale:** {p['persona_match_rationale']}\n")
            f.write(f"- **Core Functional Focus:** {p['core_functional_focus']}\n")
            f.write(f"- **Official Career Portal:** [{p['career_portal_url']}]({p['career_portal_url']})\n")
            if p['network_contacts'] and p['network_contacts'] != "Direct Portal / Professional Network":
                f.write(f"- **Network Contacts:** `{p['network_contacts']}`\n")
            f.write(f"- **Overview:** {p['company_overview']}\n\n")

    # ── Write india_gcc_landscape.md ─────────────────────────────────────────
    gcc_md = OUTPUT_DIR / "india_gcc_landscape.md"
    print(f"Writing {gcc_md}...")
    gcc_records = [r for r in all_records if r["gcc_india_hub"] != r["company_name"] or r["core_functional_focus"] != "Data Engineering, Analytics & Technology Systems"]
    with open(gcc_md, "w", encoding="utf-8") as f:
        f.write("# India Global Capability Centers (GCC) & Tech Hubs Landscape\n\n")
        f.write(f"Total Dedicated GCC Entities Profiled: **{len(gcc_records)}**\n\n")
        f.write("| Company | GCC / Entity Name | Primary Locations | Functional Focus | Career Portal |\n")
        f.write("| :--- | :--- | :--- | :--- | :--- |\n")
        for g in sorted(gcc_records, key=lambda x: x["company_name"]):
            portal_link = f"[Careers]({g['career_portal_url']})"
            f.write(f"| **{g['company_name']}** | {g['gcc_india_hub']} | {g['india_locations']} | {g['core_functional_focus']} | {portal_link} |\n")

    # ── Write all_companies_catalog.md ───────────────────────────────────────
    catalog_md = OUTPUT_DIR / "all_companies_catalog.md"
    print(f"Writing {catalog_md}...")
    with open(catalog_md, "w", encoding="utf-8") as f:
        f.write("# Master Companies MDM Directory (All India Employers)\n\n")
        f.write(f"Comprehensive directory of all **{len(all_records)}** canonical employers extracted and researched, categorized across 7 core domain pillars.\n\n")

        pillars_map = [
            ("1. Healthcare, Pharma, MedTech & Life Sciences", pharma_records),
            ("2. Strategy & Technology Consulting", consulting_records),
            ("3. AI Systems & Data Engineering", ai_records),
            ("4. E-Commerce, D2C & Retail Tech", ecom_records),
            ("5. Fintech, BFSI & Quantitative Trading", fintech_records),
            ("6. Enterprise SaaS & Cloud Platforms", saas_records),
            ("7. Industrial Tech, Conglomerates & Automotive", industrial_records),
        ]

        for p_title, records in pillars_map:
            f.write(f"## {p_title} ({len(records)} Companies)\n\n")
            f.write("| Company | Sub-Domain | Target Role Alignment | Fit | Locations | Career Link |\n")
            f.write("| :--- | :--- | :--- | :---: | :--- | :--- |\n")
            for c in records:
                portal_link = f"[Portal]({c['career_portal_url']})"
                f.write(f"| **{c['company_name']}** | {c['sub_domain']} | {c['recommended_target_roles']} | `{c['candidate_fit_score']}%` | {c['india_locations']} | {portal_link} |\n")
            f.write("\n---\n\n")

    # ── Write README.md ──────────────────────────────────────────────────────
    readme_md = OUTPUT_DIR / "README.md"
    print(f"Writing {readme_md}...")
    with open(readme_md, "w", encoding="utf-8") as f:
        f.write("# Master Data Management (MDM) Repository: India Job Discovery\n\n")
        f.write("A structured, categorized Master Data Management repository synthesizing all major employers, Global Capability Centers (GCCs), alumni contacts, and career portals in India.\n\n")
        f.write("## 📊 Repository Summary Statistics\n\n")
        f.write(f"- **Total Distinct Companies Profiled:** {len(all_records)}\n")
        f.write(f"- **Healthcare, Pharma, MedTech & Life Sciences Hubs:** {len(pharma_records)}\n")
        f.write(f"- **Total India GCCs & Tech R&D Centers Mapped:** {len(gcc_records)}\n")
        f.write(f"- **Candidate Fit Focus:** {candidate_name} ({candidate_yoe} YOE, Data Engineering, Commercial Healthcare Analytics, AI Systems)\n\n")

        f.write("## 🏛️ Domain Pillars Breakdown\n\n")
        f.write("| Domain Pillar | Companies Count | Priority Tier | Core Candidate Alignment |\n")
        f.write("| :--- | :---: | :---: | :--- |\n")
        f.write(f"| **[Healthcare, Pharma, MedTech & Life Sciences](file://{OUTPUT_DIR}/pharma_medtech_lifesciences.md)** | **{len(pharma_records)}** | `Tier 1 (Highest: 98%)` | ZS Associates Healthcare Commercial Analytics, HIPAA, HCP/HCO, Claims |\n")
        f.write(f"| **[Strategy & Technology Consulting](file://{OUTPUT_DIR}/all_companies_catalog.md#2-strategy--technology-consulting)** | **{len(consulting_records)}** | `Tier 1 (95%)` | Analytics Advisory, Solutions Architecture, Multi-vendor ETL |\n")
        f.write(f"| **[AI Systems & Data Engineering](file://{OUTPUT_DIR}/all_companies_catalog.md#3-ai-systems--data-engineering)** | **{len(ai_records)}** | `Tier 1 (94%)` | PySpark, SQL, Airflow, Agentic Pipelines, Snowflake, Big Data |\n")
        f.write(f"| **[E-Commerce, D2C & Retail Tech](file://{OUTPUT_DIR}/all_companies_catalog.md#4-e-commerce-d2c--retail-tech)** | **{len(ecom_records)}** | `Tier 2 (93%)` | Rush by Kira Logistics Reconciliation, Multi-store SKU, Conversion BI |\n")
        f.write(f"| **[Fintech, BFSI & Quantitative Trading](file://{OUTPUT_DIR}/all_companies_catalog.md#5-fintech-bfsi--quantitative-trading)** | **{len(fintech_records)}** | `Tier 2 (91%)` | TresVista Valuation, DCF/Comps, Financial Analytics, Payments |\n")
        f.write(f"| **[Enterprise SaaS & Cloud Platforms](file://{OUTPUT_DIR}/all_companies_catalog.md#6-enterprise-saas--cloud-platforms)** | **{len(saas_records)}** | `Tier 2 (90%)` | Cloud Data Warehousing, B2B Infrastructure, Observability |\n")
        f.write(f"| **[Industrial Tech, Conglomerates & Automotive](file://{OUTPUT_DIR}/all_companies_catalog.md#7-industrial-tech-conglomerates--automotive)** | **{len(industrial_records)}** | `Tier 3 (88%)` | Global Engineering Centers, IoT, Systems Optimization |\n\n")

        f.write("## 📁 Repository Structure\n\n")
        f.write(f"- [`master_companies_mdm.csv`](file://{csv_file}): Full tabular MDM dataset with candidate match rationales & locations (no LinkedIn links).\n")
        f.write(f"- [`master_companies_mdm.json`](file://{json_file}): Programmatic JSON representation for automated ATS matching & ingestion.\n")
        f.write(f"- [`pharma_medtech_lifesciences.md`](file://{pharma_md}): Complete deep dive into 130+ pharma, biotech, medical technology, and payer analytics employers in India.\n")
        f.write(f"- [`india_gcc_landscape.md`](file://{gcc_md}): Complete directory of 200+ India Global Capability Centers & Technology Hubs.\n")
        f.write(f"- [`all_companies_catalog.md`](file://{catalog_md}): Categorized employer directory across all 7 pillars.\n")

    print("Master Job Discovery MDM repository successfully generated!")


if __name__ == "__main__":
    main()
