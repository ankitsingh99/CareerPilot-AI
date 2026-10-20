#!/usr/bin/env python3
"""
JobRadar Local Dashboard with Master Companies (MDM) Integration

Zero-dependency local web dashboard that queries `jobs.db` and `master_companies_mdm.csv`
serving a rich, modern, glassmorphism-themed UI to search, filter, and review jobs
and explore target GCCs/companies.

Usage:
  python tools/jobradar_dashboard.py [--port 8765]

Author: Ankit Kumar Singh
Rule: Zero em dashes permitted. Zero paid API tokens.
"""

import os
import sys
import csv
import json
import sqlite3
import argparse
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "jobs.db"
MDM_PATH = REPO_ROOT / "job_discovery" / "master_companies_mdm.csv"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobRadar | AI Job Search & MDM Radar</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0f172a;
            --surface-color: rgba(30, 41, 59, 0.7);
            --surface-border: rgba(255, 255, 255, 0.1);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #3b82f6;
            --accent-hover: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --purple: #a855f7;
        }

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        /* Glassmorphism Background Elements */
        .bg-orb {
            position: fixed;
            border-radius: 50%;
            filter: blur(100px);
            z-index: -1;
            opacity: 0.5;
            pointer-events: none;
        }
        .orb-1 {
            top: -100px;
            left: -100px;
            width: 400px;
            height: 400px;
            background: #3b82f6;
        }
        .orb-2 {
            bottom: -100px;
            right: -100px;
            width: 500px;
            height: 500px;
            background: #8b5cf6;
        }

        header {
            padding: 1.25rem 2rem;
            background: var(--surface-color);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 1.5rem;
        }

        .logo {
            font-size: 1.4rem;
            font-weight: 700;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 10px;
            cursor: pointer;
        }

        .nav-tabs {
            display: flex;
            gap: 0.5rem;
            background: rgba(15, 23, 42, 0.6);
            padding: 0.25rem;
            border-radius: 10px;
            border: 1px solid var(--surface-border);
        }

        .nav-tab {
            padding: 0.5rem 1rem;
            border-radius: 8px;
            border: none;
            background: transparent;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .nav-tab.active {
            background: var(--accent);
            color: #ffffff;
            box-shadow: 0 2px 8px rgba(59, 130, 246, 0.4);
        }

        .header-actions {
            display: flex;
            gap: 1rem;
            align-items: center;
        }

        .btn-scan {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            padding: 0.65rem 1.25rem;
            border-radius: 8px;
            border: none;
            font-weight: 600;
            font-size: 0.85rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        .btn-scan:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 16px rgba(59, 130, 246, 0.4);
        }

        .controls {
            display: flex;
            gap: 1rem;
            align-items: center;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }

        input[type="text"], select {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--surface-border);
            color: var(--text-main);
            padding: 0.75rem 1rem;
            border-radius: 8px;
            font-family: inherit;
            font-size: 0.9rem;
            transition: all 0.3s ease;
            outline: none;
        }

        input[type="text"] {
            flex: 1;
            min-width: 250px;
        }

        input[type="text"]:focus, select:focus {
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
        }

        main {
            padding: 2rem;
            flex: 1;
            max-width: 1400px;
            margin: 0 auto;
            width: 100%;
        }

        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--surface-color);
            backdrop-filter: blur(12px);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 1.25rem;
            text-align: center;
            transition: transform 0.3s ease;
        }
        .stat-card:hover {
            transform: translateY(-3px);
        }

        .stat-value {
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
            color: #60a5fa;
        }

        .stat-label {
            color: var(--text-muted);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .cards-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 1.5rem;
        }

        .item-card {
            background: var(--surface-color);
            backdrop-filter: blur(12px);
            border: 1px solid var(--surface-border);
            border-radius: 16px;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
            animation: fadeIn 0.4s ease-out forwards;
        }

        .item-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(to right, var(--accent), #c084fc);
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .item-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
            border-color: rgba(255, 255, 255, 0.2);
        }

        .item-card:hover::before {
            opacity: 1;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 0.75rem;
            gap: 0.5rem;
        }

        .company-name {
            font-size: 0.85rem;
            color: #93c5fd;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .card-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin: 0.4rem 0;
            line-height: 1.4;
            color: var(--text-main);
        }

        .score-badge {
            background: rgba(16, 185, 129, 0.15);
            color: var(--success);
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 0.25rem 0.65rem;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            white-space: nowrap;
        }
        
        .score-badge.medium {
            background: rgba(245, 158, 11, 0.15);
            color: var(--warning);
            border-color: rgba(245, 158, 11, 0.3);
        }
        
        .score-badge.low {
            background: rgba(239, 68, 68, 0.15);
            color: var(--danger);
            border-color: rgba(239, 68, 68, 0.3);
        }

        .tags-container {
            display: flex;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-bottom: 1.25rem;
        }

        .tag {
            background: rgba(255, 255, 255, 0.06);
            padding: 0.25rem 0.6rem;
            border-radius: 6px;
            font-size: 0.75rem;
            color: var(--text-muted);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }

        .tag.pillar {
            color: #c084fc;
            background: rgba(168, 85, 247, 0.1);
            border-color: rgba(168, 85, 247, 0.2);
        }

        .card-snippet {
            font-size: 0.85rem;
            color: #cbd5e1;
            line-height: 1.5;
            margin-bottom: 1.25rem;
            flex: 1;
        }

        .card-actions {
            margin-top: auto;
            display: flex;
            gap: 0.75rem;
        }

        .btn {
            flex: 1;
            padding: 0.65rem;
            border: none;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-align: center;
            text-decoration: none;
            font-size: 0.85rem;
            display: inline-block;
        }

        .btn-primary {
            background: var(--accent);
            color: white;
        }

        .btn-primary:hover {
            background: var(--accent-hover);
            transform: scale(1.02);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.08);
            color: var(--text-main);
            border: 1px solid var(--surface-border);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.15);
        }
        
        .loading {
            text-align: center;
            padding: 4rem;
            font-size: 1.2rem;
            color: var(--text-muted);
            grid-column: 1 / -1;
        }

        .toast {
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid var(--accent);
            padding: 1rem 1.5rem;
            border-radius: 10px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            z-index: 1000;
            animation: fadeIn 0.3s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body>
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>

    <header>
        <div class="logo-area">
            <div class="logo" onclick="switchTab('jobs')">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="2" x2="12" y2="12"></line>
                    <line x1="12" y1="12" x2="19" y2="12"></line>
                </svg>
                JobRadar
            </div>
            <div class="nav-tabs">
                <button class="nav-tab active" id="tabJobs" onclick="switchTab('jobs')">Live Stream (Roles)</button>
                <button class="nav-tab" id="tabCompanies" onclick="switchTab('companies')">Target Companies (MDM)</button>
            </div>
        </div>
        <div class="header-actions">
            <button class="btn-scan" onclick="triggerScan()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                Scan Target Boards
            </button>
        </div>
    </header>

    <main>
        <!-- Jobs View -->
        <div id="viewJobs">
            <div class="stats-bar">
                <div class="stat-card">
                    <div class="stat-value" id="totalJobs">0</div>
                    <div class="stat-label">Discovered Roles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="topMatches">0</div>
                    <div class="stat-label">High Fit (85%+)</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="remoteJobs">0</div>
                    <div class="stat-label">Remote / NCR Roles</div>
                </div>
            </div>

            <div class="controls">
                <input type="text" id="jobSearch" placeholder="Search role title or company..." oninput="filterJobs()">
                <select id="jobScoreFilter" onchange="filterJobs()">
                    <option value="0">All Scores</option>
                    <option value="80" selected>Score 80%+</option>
                    <option value="90">Score 90%+</option>
                    <option value="95">Score 95%+</option>
                </select>
                <select id="jobSectorFilter" onchange="filterJobs()">
                    <option value="all">All Sectors</option>
                    <option value="Healthcare">Healthcare & Life Sciences</option>
                    <option value="AI">AI Systems & Data Engineering</option>
                    <option value="Consulting">Strategy & Consulting</option>
                    <option value="Fintech">Fintech & BFSI</option>
                    <option value="E-Commerce">E-Commerce & Retail</option>
                </select>
            </div>

            <div class="cards-grid" id="jobsGrid">
                <div class="loading">Loading live discovered roles...</div>
            </div>
        </div>

        <!-- Companies View -->
        <div id="viewCompanies" style="display: none;">
            <div class="stats-bar">
                <div class="stat-card">
                    <div class="stat-value" id="totalCompanies">0</div>
                    <div class="stat-label">Target Companies</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="healthcareCount">0</div>
                    <div class="stat-label">Healthcare & Pharma</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="aiCount">0</div>
                    <div class="stat-label">AI Systems & Data</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" id="consultingCount">0</div>
                    <div class="stat-label">Strategy Consulting</div>
                </div>
            </div>

            <div class="controls">
                <input type="text" id="companySearch" placeholder="Search 590+ target companies, hubs, or skills..." oninput="filterCompanies()">
                <select id="pillarFilter" onchange="filterCompanies()">
                    <option value="all">All Domain Pillars</option>
                    <option value="Healthcare">Healthcare, Pharma & MedTech</option>
                    <option value="AI Systems">AI Systems & Data Engineering</option>
                    <option value="Strategy">Strategy & Technology Consulting</option>
                    <option value="Fintech">Fintech & BFSI</option>
                    <option value="E-Commerce">E-Commerce & D2C</option>
                </select>
                <select id="locationFilter" onchange="filterCompanies()">
                    <option value="all">All Locations</option>
                    <option value="Delhi">Delhi NCR / Noida / Gurgaon</option>
                    <option value="Bengaluru">Bengaluru / Bangalore</option>
                    <option value="Hyderabad">Hyderabad</option>
                    <option value="Remote">Remote</option>
                </select>
            </div>

            <div class="cards-grid" id="companiesGrid">
                <div class="loading">Loading Master Companies MDM Directory...</div>
            </div>
        </div>
    </main>

    <div id="toastContainer"></div>

    <script>
        let allJobs = [];
        let allCompanies = [];
        let currentTab = 'jobs';

        function showToast(msg) {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = 'toast';
            toast.textContent = msg;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 4000);
        }

        function switchTab(tab) {
            currentTab = tab;
            document.getElementById('tabJobs').classList.toggle('active', tab === 'jobs');
            document.getElementById('tabCompanies').classList.toggle('active', tab === 'companies');
            document.getElementById('viewJobs').style.display = tab === 'jobs' ? 'block' : 'none';
            document.getElementById('viewCompanies').style.display = tab === 'companies' ? 'block' : 'none';
            if (tab === 'companies' && allCompanies.length === 0) {
                fetchCompanies();
            }
        }

        async function fetchJobs() {
            try {
                const res = await fetch('/api/jobs');
                allJobs = await res.json();
                updateJobStats();
                filterJobs();
            } catch (e) {
                document.getElementById('jobsGrid').innerHTML = `<div class="loading" style="color: var(--danger)">Error loading jobs. Ensure server is active.</div>`;
            }
        }

        async function fetchCompanies() {
            try {
                const res = await fetch('/api/companies');
                allCompanies = await res.json();
                updateCompanyStats();
                filterCompanies();
            } catch (e) {
                document.getElementById('companiesGrid').innerHTML = `<div class="loading" style="color: var(--danger)">Error loading companies catalog.</div>`;
            }
        }

        async function triggerScan() {
            showToast("⚡ Initiating background ATS poll for MDM target companies...");
            try {
                const res = await fetch('/api/poll-mdm', { method: 'POST' });
                const data = await res.json();
                showToast(data.message || "Scan complete!");
                fetchJobs();
            } catch (e) {
                showToast("Scan finished or running in background. Refreshing...");
                setTimeout(fetchJobs, 3000);
            }
        }

        function updateJobStats() {
            document.getElementById('totalJobs').textContent = allJobs.length;
            document.getElementById('topMatches').textContent = allJobs.filter(j => j.score >= 85).length;
            document.getElementById('remoteJobs').textContent = allJobs.filter(j => 
                (j.location || '').toLowerCase().includes('remote') || 
                (j.location || '').toLowerCase().includes('ncr') || 
                (j.location || '').toLowerCase().includes('delhi')
            ).length;
        }

        function updateCompanyStats() {
            document.getElementById('totalCompanies').textContent = allCompanies.length;
            document.getElementById('healthcareCount').textContent = allCompanies.filter(c => (c.domain_pillar || '').includes('Healthcare')).length;
            document.getElementById('aiCount').textContent = allCompanies.filter(c => (c.domain_pillar || '').includes('AI Systems')).length;
            document.getElementById('consultingCount').textContent = allCompanies.filter(c => (c.domain_pillar || '').includes('Strategy')).length;
        }

        function filterJobs() {
            const q = document.getElementById('jobSearch').value.toLowerCase();
            const minScore = parseFloat(document.getElementById('jobScoreFilter').value) || 0;
            const sec = document.getElementById('jobSectorFilter').value;

            const filtered = allJobs.filter(j => {
                const matchQ = (j.title || '').toLowerCase().includes(q) || (j.company || '').toLowerCase().includes(q) || (j.location || '').toLowerCase().includes(q);
                const matchScore = (j.score || 0) >= minScore;
                const matchSec = sec === 'all' || (j.sector || '').toLowerCase().includes(sec.toLowerCase());
                return matchQ && matchScore && matchSec;
            });

            filtered.sort((a, b) => (b.score || 0) - (a.score || 0));
            renderJobs(filtered);
        }

        function renderJobs(jobs) {
            const grid = document.getElementById('jobsGrid');
            grid.innerHTML = '';
            if (jobs.length === 0) {
                grid.innerHTML = '<div class="loading">No matching roles found. Try adjusting filters or click "Scan Target Boards".</div>';
                return;
            }

            jobs.forEach((j, i) => {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.style.animationDelay = `${Math.min(i * 0.03, 0.5)}s`;

                const fitScore = Math.round(j.score || 0);
                const scoreClass = fitScore >= 90 ? '' : (fitScore >= 80 ? 'medium' : 'low');

                card.innerHTML = `
                    <div class="card-header">
                        <div class="company-name">${j.company}</div>
                        <div class="score-badge ${scoreClass}">${fitScore}% Fit</div>
                    </div>
                    <div class="card-title">${j.title}</div>
                    <div class="tags-container">
                        <span class="tag">📍 ${j.location || 'Remote / Unspecified'}</span>
                        ${j.sector ? `<span class="tag pillar">🏛️ ${j.sector.split('&')[0].trim()}</span>` : ''}
                        <span class="tag">📝 ${j.status || 'discovered'}</span>
                    </div>
                    <div class="card-actions">
                        <a href="${j.url}" target="_blank" class="btn btn-primary">Apply on ATS</a>
                        ${j.recruiter_search_link ? `<a href="${j.recruiter_search_link}" target="_blank" class="btn btn-secondary">Find Recruiter</a>` : ''}
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        function filterCompanies() {
            const q = document.getElementById('companySearch').value.toLowerCase();
            const pillar = document.getElementById('pillarFilter').value;
            const loc = document.getElementById('locationFilter').value.toLowerCase();

            const filtered = allCompanies.filter(c => {
                const matchQ = (c.company_name || '').toLowerCase().includes(q) || 
                               (c.gcc_india_hub || '').toLowerCase().includes(q) || 
                               (c.core_functional_focus || '').toLowerCase().includes(q) ||
                               (c.recommended_target_roles || '').toLowerCase().includes(q);
                const matchPillar = pillar === 'all' || (c.domain_pillar || '').toLowerCase().includes(pillar.toLowerCase());
                const matchLoc = loc === 'all' || (c.india_locations || '').toLowerCase().includes(loc);
                return matchQ && matchPillar && matchLoc;
            });

            filtered.sort((a, b) => (parseFloat(b.candidate_fit_score) || 0) - (parseFloat(a.candidate_fit_score) || 0));
            renderCompanies(filtered);
        }

        function renderCompanies(comps) {
            const grid = document.getElementById('companiesGrid');
            grid.innerHTML = '';
            if (comps.length === 0) {
                grid.innerHTML = '<div class="loading">No companies found matching search criteria.</div>';
                return;
            }

            comps.forEach((c, i) => {
                const card = document.createElement('div');
                card.className = 'item-card';
                card.style.animationDelay = `${Math.min(i * 0.03, 0.5)}s`;

                const fitScore = Math.round(parseFloat(c.candidate_fit_score) || 90);
                const scoreClass = fitScore >= 94 ? '' : (fitScore >= 85 ? 'medium' : 'low');

                card.innerHTML = `
                    <div class="card-header">
                        <div class="company-name">${c.domain_pillar ? c.domain_pillar.split(',')[0] : 'Enterprise'}</div>
                        <div class="score-badge ${scoreClass}">${fitScore}% Fit</div>
                    </div>
                    <div class="card-title">${c.company_name}</div>
                    <div class="tags-container">
                        <span class="tag">📍 ${c.india_locations || 'India Hub'}</span>
                        ${c.compensation_median_lpa ? `<span class="tag">💰 ₹${c.compensation_median_lpa} LPA Median</span>` : ''}
                        ${c.sub_domain ? `<span class="tag pillar">🔬 ${c.sub_domain}</span>` : ''}
                    </div>
                    <div class="card-snippet">
                        <strong>Target Roles:</strong> ${c.recommended_target_roles || 'Data Engineer, Analytics Consultant'}<br>
                        <span style="color: var(--text-muted); font-size: 0.8rem; margin-top: 4px; display: block;">${c.core_functional_focus || ''}</span>
                    </div>
                    <div class="card-actions">
                        ${c.career_portal_url ? `<a href="${c.career_portal_url}" target="_blank" class="btn btn-primary">Career Portal</a>` : ''}
                        <a href="https://www.linkedin.com/search/results/people/?keywords=${encodeURIComponent(c.company_name + ' recruiter')}" target="_blank" class="btn btn-secondary">Recruiters</a>
                    </div>
                `;
                grid.appendChild(card);
            });
        }

        document.addEventListener('DOMContentLoaded', () => {
            fetchJobs();
            fetchCompanies();
        });
    </script>
</body>
</html>
"""

class JobRadarHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
            
        elif parsed.path == '/api/jobs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            jobs = []
            if DB_PATH.exists():
                try:
                    conn = sqlite3.connect(DB_PATH)
                    conn.row_factory = sqlite3.Row
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM jobs ORDER BY score DESC, id DESC")
                    for r in cursor.fetchall():
                        jobs.append({
                            "id": r["id"],
                            "company": r["company"],
                            "sector": r["sector"] if "sector" in r.keys() else "",
                            "title": r["title"],
                            "url": r["url"],
                            "location": r["location"],
                            "salary": r["salary"] if "salary" in r.keys() else "",
                            "score": round(r["score"], 1) if r["score"] else 0,
                            "status": r["status"] or "discovered",
                            "recruiter_search_link": r["recruiter_search_link"] if "recruiter_search_link" in r.keys() else ""
                        })
                    conn.close()
                except Exception as e:
                    print(f"DB Error: {e}")
                    
            self.wfile.write(json.dumps(jobs).encode('utf-8'))

        elif parsed.path == '/api/companies':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            companies = []
            if MDM_PATH.exists():
                try:
                    with open(MDM_PATH, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            companies.append(row)
                except Exception as e:
                    print(f"MDM CSV Error: {e}")

            self.wfile.write(json.dumps(companies).encode('utf-8'))

        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/poll-mdm':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Trigger background scan
            try:
                subprocess.Popen([sys.executable, str(REPO_ROOT / "tools" / "poll_mdm_companies.py")])
                res = {"status": "started", "message": "Target company boards scan started in background!"}
            except Exception as e:
                res = {"status": "error", "message": str(e)}
            self.wfile.write(json.dumps(res).encode('utf-8'))
        else:
            self.send_error(404, "Not Found")

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="JobRadar Local Dashboard Server")
    parser.add_argument("--port", type=int, default=8765, help="Port to run the dashboard on")
    args = parser.parse_args()

    server = HTTPServer(('localhost', args.port), JobRadarHandler)
    print(f"🚀 JobRadar Dashboard is live at: http://localhost:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down dashboard...")
        server.server_close()


if __name__ == '__main__':
    main()
