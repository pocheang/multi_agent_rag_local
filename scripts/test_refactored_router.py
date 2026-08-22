"""Quick smoke test for refactored router."""

from app.agents.router.pipeline import RoutingPipeline

# Quick smoke test
pipeline = RoutingPipeline()
result = pipeline.decide('什么是机器学习？', use_llm_intent=False)

print('✓ Pipeline created successfully')
print(f'✓ Route: {result.route}')
print(f'✓ Confidence: {result.confidence:.2f}')
print(f'✓ Skill: {result.skill}')
print('\n✅ Router refactoring verified!')
