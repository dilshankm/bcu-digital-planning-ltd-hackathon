from typing import List, Dict, Any

import dspy
import litellm

from config import get_settings


class DSPyService:
    def __init__(self):
        settings = get_settings()
        # Drop unsupported params for OpenAI compatibility
        litellm.drop_params = True
        # Configure DSPy (v3) using generic LM interface via LiteLLM adapter
        # Using gpt-3.5-turbo for higher rate limits and lower cost
        dspy.configure(lm=dspy.LM("openai/gpt-3.5-turbo", api_key=settings.openai_api_key))

        # Define multi-agent signatures
        class PlanSignature(dspy.Signature):
            """Create a concise plan to answer the question using the provided graph context."""
            question = dspy.InputField()
            context = dspy.InputField()
            plan = dspy.OutputField()

        class AnalystSignature(dspy.Signature):
            """Draft a user-friendly answer using ONLY the data provided. BANNED WORDS: Cypher, query, database, graph, nodes, relationships, context, "based on", "according to", "shows", "indicates". Answer like you naturally know this - just state the fact directly. Example GOOD: "There are 109 patients." Example BAD: "The number of patients in the graph context is 109." Start with the number or fact immediately."""
            question = dspy.InputField()
            context = dspy.InputField()
            plan = dspy.InputField()
            draft = dspy.OutputField()

        class CriticSignature(dspy.Signature):
            """Review the draft. Check: (1) Does it use FORBIDDEN technical words like graph, query, database, Cypher, nodes, context? (2) Does it say "based on" or "according to"? (3) Does it invent facts not in context? (4) Is it direct and simple? List all issues."""
            question = dspy.InputField()
            context = dspy.InputField()
            draft = dspy.InputField()
            critique = dspy.OutputField()

        class ImproveSignature(dspy.Signature):
            """Produce a clean, simple final answer. ABSOLUTELY FORBIDDEN WORDS: Cypher, query, database, graph, nodes, context, "based on", "according to", "the data shows". Answer like a human who naturally knows this information. Example GOOD: "There are 109 patients." Example BAD: "The number of patients in the graph context is 109." Just state facts directly. No explanations of where data came from."""
            question = dspy.InputField()
            context = dspy.InputField()
            draft = dspy.InputField()
            critique = dspy.InputField()
            answer = dspy.OutputField()

        # Instantiate agents
        self.planner = dspy.Predict(PlanSignature)
        self.analyst = dspy.Predict(AnalystSignature)
        self.critic = dspy.Predict(CriticSignature)
        self.improver = dspy.Predict(ImproveSignature)

    def answer(self, question: str, context: str) -> str:
        # Agent 1: PLANNER creates strategy
        print("\n🤖 [PLANNER AGENT] Creating plan...")
        plan_res = self.planner(question=question, context=context)
        plan = getattr(plan_res, "plan", "Use the most relevant nodes and relationships to answer.")
        print(f"   Plan: {plan[:150]}...")

        # Agent 2: ANALYST receives plan, drafts answer
        print("\n📊 [ANALYST AGENT] Drafting answer based on plan...")
        draft_res = self.analyst(question=question, context=context, plan=plan)
        draft = getattr(draft_res, "draft", "")
        print(f"   Draft: {draft[:150]}...")

        # Agent 3: CRITIC reviews analyst's draft
        print("\n🔍 [CRITIC AGENT] Reviewing draft for improvements...")
        critique_res = self.critic(question=question, context=context, draft=draft)
        critique = getattr(critique_res, "critique", "")
        print(f"   Critique: {critique[:150]}...")

        # Agent 4: IMPROVER takes draft + critique, produces final answer
        print("\n✨ [IMPROVER AGENT] Refining answer based on critique...")
        improved = self.improver(question=question, context=context, draft=draft, critique=critique)
        final_answer = getattr(improved, "answer", draft)
        print(f"   Final Answer: {final_answer[:150]}...\n")
        return final_answer


