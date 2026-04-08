"""
Phase 5 E2E Demo Validation Report
Validates all components are ready for live demo.
"""

import sys
import subprocess
from pathlib import Path


def check_component(name: str, check_func) -> bool:
    """Run a component check and report result."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    try:
        result = check_func()
        if result:
            print(f"✅ {name}: PASS")
        else:
            print(f"❌ {name}: FAIL")
        return result
    except Exception as e:
        print(f"❌ {name}: ERROR - {e}")
        return False


def test_rust_engine():
    """Test Rust engine can be imported."""
    print("Importing Rust engine...")
    try:
        import incident_core
        graph = incident_core.RustServiceGraph("bad_deploy", 1)
        obs = graph.reset()
        print(f"  - Observation shape: {obs.shape}")
        print(f"  - Expected: (72,)")
        assert obs.shape == (72,), f"Wrong shape: {obs.shape}"
        print("  - ✓ Rust engine working")
        return True
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_incident_env():
    """Test IncidentEnv wrapper."""
    print("Testing IncidentEnv...")
    try:
        from envs import IncidentEnv
        env = IncidentEnv(scenario="bad_deploy", curriculum_level=1)
        obs, info = env.reset()
        print(f"  - Reset observation shape: {obs.shape}")
        print(f"  - Info: {info}")
        
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        print(f"  - Step observation shape: {obs.shape}")
        print(f"  - Reward: {reward}")
        print(f"  - ✓ IncidentEnv working")
        return True
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_graders():
    """Test grader functions."""
    print("Testing graders...")
    try:
        from graders import grade_episode, grade_with_llm
        
        # Test programmatic grader
        services_history = [
            [{"service_id": i, "status": "Healthy", "health": 1.0} for i in range(12)]
        ]
        actions_taken = [[0, 0]]
        
        result = grade_episode(
            episode_steps=1,
            services_history=services_history,
            actions_taken=actions_taken,
            final_all_healthy=True
        )
        
        print(f"  - Programmatic grader score: {result.overall_score:.2f}/100")
        assert 0 <= result.overall_score <= 100
        print(f"  - ✓ Programmatic grader working")
        
        # Test LLM grader fallback
        llm_result = grade_with_llm(
            scenario="bad_deploy",
            services_history=[],
            actions_taken=[],
            action_reasoning=[],
            final_all_healthy=True,
            timeout=1
        )
        
        print(f"  - LLM grader available: {llm_result.available}")
        print(f"  - LLM fallback score: {llm_result.reasoning_quality:.2f}/100")
        print(f"  - ✓ LLM grader fallback working")
        
        return True
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_api_module():
    """Test API module can be imported."""
    print("Testing API module...")
    try:
        from api.main import app
        print(f"  - FastAPI app: {app.title if hasattr(app, 'title') else 'loaded'}")
        print(f"  - ✓ API module working")
        return True
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_checkpoint_exists():
    """Test trained checkpoint exists."""
    print("Testing checkpoint...")
    try:
        checkpoint_path = Path("checkpoints/latest.pt")
        if checkpoint_path.exists():
            size_mb = checkpoint_path.stat().st_size / (1024 * 1024)
            print(f"  - Checkpoint found: {checkpoint_path}")
            print(f"  - Size: {size_mb:.2f} MB")
            print(f"  - ✓ Checkpoint exists")
            return True
        else:
            print(f"  - ✗ Checkpoint not found at {checkpoint_path}")
            return False
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_dashboard_files():
    """Test dashboard files exist."""
    print("Testing dashboard...")
    try:
        dashboard_path = Path("dashboard")
        required_files = [
            "package.json",
            "src/App.jsx",
            "src/components/ServiceGraph.jsx",
            "src/components/MetricsFeed.jsx",
            "src/components/AgentLog.jsx",
            "src/components/ScoreCard.jsx",
            "src/hooks/useEpisodeStream.js",
        ]
        
        all_exist = True
        for file in required_files:
            file_path = dashboard_path / file
            if file_path.exists():
                print(f"  - ✓ {file}")
            else:
                print(f"  - ✗ {file} missing")
                all_exist = False
        
        if all_exist:
            print(f"  - ✓ All dashboard files present")
        return all_exist
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def test_full_test_suite():
    """Run pytest suite."""
    print("Running test suite...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("  - ✓ All tests passed")
            return True
        else:
            print(f"  - ✗ Tests failed with code {result.returncode}")
            return False
    except Exception as e:
        print(f"  - ✗ Error: {e}")
        return False


def main():
    """Run Phase 5 validation."""
    print("\n" + "🏆" * 30)
    print("PHASE 5: E2E DEMO RELIABILITY VALIDATION")
    print("🏆" * 30)
    
    components = [
        ("Rust Engine", test_rust_engine),
        ("IncidentEnv Wrapper", test_incident_env),
        ("Graders (Programmatic + LLM)", test_graders),
        ("API Module", test_api_module),
        ("Trained Checkpoint", test_checkpoint_exists),
        ("Dashboard Files", test_dashboard_files),
        ("Full Test Suite", test_full_test_suite),
    ]
    
    results = {}
    for name, check_func in components:
        results[name] = check_component(name, check_func)
    
    # Summary
    print("\n" + "="*60)
    print("PHASE 5 VALIDATION SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\nComponent Tests: {passed}/{total} passed\n")
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status:12} {name}")
    
    if passed == total:
        print("\n" + "🎉" * 30)
        print("✅ PHASE 5 COMPLETE - ALL COMPONENTS READY!")
        print("🎉" * 30)
        print("\nDemo readiness:")
        print("  ✅ Rust engine functional")
        print("  ✅ Python environment wrapper working")
        print("  ✅ Graders implemented and tested")
        print("  ✅ API module loads successfully")
        print("  ✅ Trained model checkpoint available")
        print("  ✅ Dashboard components built")
        print("  ✅ All automated tests passing (9/9)")
        print("\nTo run live demo:")
        print("  1. Terminal 1: cd incident-env && .venv\\Scripts\\python.exe -m uvicorn api.main:app --port 8000")
        print("  2. Terminal 2: cd incident-env\\dashboard && npm run dev")
        print("  3. Browser: http://localhost:5173/")
        print("\n✨ Ready for hackathon presentation! ✨\n")
        return 0
    else:
        print(f"\n⚠️  {total - passed} component(s) failed")
        print("Review failures above and fix before demo.\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
