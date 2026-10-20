import asyncio
import json
import re
import yaml
import os
from database.db_manager import DatabaseManager
from engine.router import DynamicModelRouter
from engine.discovery import DiscoveryEngine
from engine.tailor import DocumentTailorEngine
from engine.executor import StealthExecutor
from rich.console import Console

console = Console()

async def run_superbot_pipeline():
    console.print("[bold green]=== STARTING AI JOB APPLICATION SUPERBOT ENGINE ===[/bold green]")
    
    # Load Configurations
    with open("config/config.yaml", "r") as f:
        config = yaml.safe_load(f)
    with open("config/profile.json", "r") as f:
        profile = json.load(f)

    # Initialize System Submodules
    db = DatabaseManager()
    await db.init_db()
    
    router = DynamicModelRouter(config)
    discovery = DiscoveryEngine(config)
    tailor = DocumentTailorEngine(profile)
    executor = StealthExecutor(config['system']['persistent_user_data_dir'], config['system']['headless_browser'])

    # 1. Fetch Job Postings
    console.print("\n[bold blue]1. Running Discovery Scraper...[/bold blue]")
    raw_jobs = await discovery.fetch_mock_jobs()

    for job in raw_jobs:
        job_hash = db.generate_hash(job['title'], job['company'], job['description'])

        # 2. Cache Deduplication Check
        if await db.is_processed(job_hash):
            console.print(f"[yellow][CACHE HIT] Skipping previously evaluated job: {job['title']} at {job['company']}[/yellow]")
            continue

        # 3. Deterministic Local Filter
        if not discovery.is_rule_compliant(job['title'], job['location']):
            console.print(f"[red][RULE REJECT] Failed title/location filters: {job['title']} ({job['location']})[/red]")
            # estimate token usage for rule check (title + location)
            token_counter["filter"] += estimate_tokens(job['title'] + " " + job['location'])
            token_counter["total"] += token_counter["filter"]
            await db.save_job(job_hash, job['job_id'], job['source'], job['title'], job['company'], job['location'], 0, "RULE_REJECTED", {})
            continue

        # 4. Semantic Fit Scoring (Tier 2 Call)
        model_name = router.route_task("score", token_estimate=800)
        console.print(f"[cyan][EVALUATION] Scoring fit for '{job['title']}' using model {model_name}...[/cyan]")
        
        # Simulated Fit Score
        fit_score = 85

        if fit_score < config['system']['fit_threshold']:
            console.print(f"[red][LOW FIT] Score {fit_score} below threshold {config['system']['fit_threshold']}[/red]")
            await db.save_job(job_hash, job['job_id'], job['source'], job['title'], job['company'], job['location'], fit_score, "LOW_SCORE_REJECTED", {})
            continue

        # 5. Tailor Documents (Tier 3 Call)
        console.print(f"[magenta][TAILORING] Generating custom resume bullets & cover letter...[/magenta]")
        tailored_materials = tailor.generate_tailored_materials(job['title'], job['company'], job['description'])

        application_payload = {
            "candidate_name": f"{profile['personal_info']['first_name']} {profile['personal_info']['last_name']}",
            "job_title": job['title'],
            "company": job['company'],
            "apply_url": job['apply_url'],
            "materials": tailored_materials
        }

        # 6. Human-in-the-Loop (HITL) Gate
        approval_file = f"pending_approvals/{job_hash}.json"
        os.makedirs(os.path.dirname(approval_file), exist_ok=True)
        with open(approval_file, "w") as f:
            json.dump(application_payload, f, indent=2)

        autonomy_mode = config['system'].get('autonomy_mode', 'review-each')
        
        if autonomy_mode == 'routine-auto':
            console.print(f"\n[bold green]>>> AUTONOMY MODE ACTIVE: Auto-approving application for '{job['title']}' <<<[/bold green]")
            user_choice = 'yes'
        else:
            console.print(f"\n[bold yellow]>>> HITL GATE: Application staged for approval at {approval_file} <<<[/bold yellow]")
            user_choice = input(f"Approve application for '{job['title']}' at '{job['company']}'? (yes/no): ").strip().lower()

        if user_choice in ["y", "yes"]:
            # 7. Stealth Execution
            console.print(f"[bold green][EXECUTING] Launching Stealth Playwright Driver...[/bold green]")
            execution_status = await executor.execute_application(job['apply_url'], application_payload)
            token_counter["execution"] += estimate_tokens(json.dumps(application_payload))
            token_counter["total"] += token_counter["execution"]
            await db.save_job(job_hash, job['job_id'], job['source'], job['title'], job['company'], job['location'], fit_score, execution_status, application_payload)
        else:
            console.print(f"[yellow][HITL REJECT] User rejected application.[/yellow]")
            await db.save_job(job_hash, job['job_id'], job['source'], job['title'], job['company'], job['location'], fit_score, "HITL_REJECTED", application_payload)

    console.print("\n[bold green]=== SUPERBOT CYCLE COMPLETE ===[/bold green]")
    
    # # Token usage summary
    # console.print("\n[bold cyan]=== TOKEN USAGE SUMMARY ===[/bold cyan]")
    # for step, count in token_counter.items():
    #     console.print(f"{step}: {count} tokens")

if __name__ == "__main__":
    asyncio.run(run_superbot_pipeline())
