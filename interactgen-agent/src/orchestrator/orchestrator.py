"""
Main orchestrator for coordinating all components.
Provides both sync (CLI) and async (chatbot) execution modes.
"""
import json
import os
from typing import Dict, List, Any, Optional
from pathlib import Path


class Orchestrator:
    """Coordinates scraper, planner, selector, and executor components."""
    
    def __init__(self, groq_api_key: Optional[str] = None):
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY")
        if not self.groq_api_key:
            raise ValueError("GROQ_API_KEY required")
    
    def execute_query_sync(self, query: str, url: str, output_dir: str = "logs") -> Dict[str, Any]:
        """
        Execute a query synchronously (for CLI use).
        
        Args:
            query: Natural language query
            url: Target website URL
            output_dir: Directory for output files
        
        Returns:
            Results dictionary with steps, candidates, and execution results
        """
        from src.scraper.fast_snapshot import snapshot
        from src.planner.planner_agent import plan_with_groq
        from src.selector.selector import select_candidates_hybrid
        from src.executor.executor import execute_step
        from playwright.sync_api import sync_playwright
        
        # Create output directory
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Step 1: Scrape
        print(f"[1/4] Scraping {url}...")
        snapshot_path = f"{output_dir}/snapshot.json"
        snapshot(url, snapshot_path)
        
        with open(snapshot_path, 'r') as f:
            snapshot_data = json.load(f)
        
        # Step 2: Plan
        print(f"[2/4] Planning steps for: {query}")
        steps = plan_with_groq(query, url, snapshot_data, self.groq_api_key)
        
        steps_path = f"{output_dir}/steps.json"
        with open(steps_path, 'w') as f:
            json.dump(steps, f, indent=2)
        
        # Step 3: Select candidates
        print(f"[3/4] Selecting element candidates...")
        all_candidates = {}
        
        for step in steps:
            if step.get('action') in ['click', 'type', 'extract']:
                target = step.get('target', '')
                visual_hint = step.get('visual_hint')
                candidates = select_candidates_hybrid(snapshot_data, target, visual_hint, 3)
                all_candidates[step['step_id']] = {
                    "target": target,
                    "candidates": candidates
                }
        
        candidates_path = f"{output_dir}/candidates.json"
        with open(candidates_path, 'w') as f:
            json.dump(all_candidates, f, indent=2)
        
        # Step 4: Execute
        print(f"[4/4] Executing {len(steps)} steps...")
        
        results = []
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            for step in steps:
                step_id = step['step_id']
                print(f"  [{step_id}] {step.get('action')} - {step.get('target', 'N/A')}")
                
                candidates = all_candidates.get(step_id, {}).get('candidates', [])
                
                # Import executor function
                from src.executor.executor import execute_step
                result = execute_step(page, step, candidates)
                results.append(result)
                
                if not result['ok']:
                    print(f"    ✗ Failed: {result.get('reason')}")
                    # Could break here or continue
            
            browser.close()
        
        # Summary
        passed = sum(1 for r in results if r['ok'])
        total = len(results)
        avg_time = sum(r['time_ms'] for r in results) / total if results else 0
        
        summary = {
            "query": query,
            "url": url,
            "steps": steps,
            "candidates": all_candidates,
            "results": results,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "avg_time_ms": avg_time
            }
        }
        
        # Save results
        results_path = f"{output_dir}/results.json"
        with open(results_path, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n{'='*60}")
        print(f"Results: {passed}/{total} steps passed")
        print(f"Average time: {avg_time:.1f}ms per step")
        print(f"Saved to {results_path}")
        
        return summary


def main():
    """CLI entry point for orchestrator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run complete automation workflow")
    parser.add_argument("--query", required=True, help="Natural language query")
    parser.add_argument("--url", required=True, help="Target website URL")
    parser.add_argument("--output", "-o", default="logs", help="Output directory")
    
    args = parser.parse_args()
    
    orchestrator = Orchestrator()
    orchestrator.execute_query_sync(args.query, args.url, args.output)


if __name__ == "__main__":
    main()
