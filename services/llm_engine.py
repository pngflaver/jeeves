import logging
from typing import List, Dict, Optional
import ollama
import config

logger = logging.getLogger(__name__)

class LLMEngine:
    def __init__(self):
        self.client = ollama.AsyncClient(host=config.OLLAMA_HOST)
        self.model = config.OLLAMA_MODEL
        self.system_prompt = config.SYSTEM_PROMPT
        self.max_tokens = config.MAX_RESPONSE_TOKENS
        self.temperature = config.TEMPERATURE

    async def generate_response(
        self,
        user_prompt: str,
        context_messages: Optional[List[Dict[str, str]]] = None,
        wiki_info: Optional[Dict[str, str]] = None,
        search_results: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """
        Generate an expanded, evidence-based response using search results or Wikipedia.
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add recent conversation context (last 4 messages)
        if context_messages:
            messages.extend(context_messages[-4:])

        # Build prompt with optional live search or Wikipedia context
        final_prompt = user_prompt
        if search_results:
            snippets_formatted = "\n\n".join([
                f"Source {i+1}: {r.get('title')}\nURL: {r.get('url')}\nContent: {r.get('snippet')}"
                for i, r in enumerate(search_results)
            ])
            search_context = (
                f"[Live Web Search & Technical Documentation Reference]\n"
                f"{snippets_formatted}\n"
                f"[End of Reference]\n\n"
                f"User Question: {user_prompt}"
            )
            final_prompt = search_context
        elif wiki_info:
            wiki_snippet = (
                f"[Wikipedia Reference Information]\n"
                f"Title: {wiki_info.get('title')}\n"
                f"Summary: {wiki_info.get('extract')}\n"
                f"[End of Reference]\n\n"
                f"User Question: {user_prompt}"
            )
            final_prompt = wiki_snippet

        messages.append({"role": "user", "content": final_prompt})

        try:
            response = await self.client.chat(
                model=self.model,
                messages=messages,
                options={
                    "num_predict": self.max_tokens,
                    "temperature": self.temperature,
                }
            )
            content = response.get("message", {}).get("content", "").strip()
            if not content:
                return "No response generated."

            # Ensure Source Links are attached when search_results are present
            if search_results:
                valid_links = [
                    f"• [{r.get('title', 'Source')[:50]}]({r.get('url')})"
                    for r in search_results if r.get('url')
                ]
                if valid_links:
                    sources_str = "\n\n🌐 **Official / Referenced Sources:**\n" + "\n".join(valid_links[:3])
                    # Only append if links not already embedded
                    if not any(r.get('url') in content for r in search_results if r.get('url')):
                        content += sources_str

            # Ensure Wikipedia citation link is attached when wiki_info was retrieved
            elif wiki_info and wiki_info.get("url"):
                wiki_title = wiki_info.get("title", "Article")
                wiki_url = wiki_info.get("url")
                citation = f"\n\n🔗 *Wikipedia:* [{wiki_title}]({wiki_url})"
                if wiki_url not in content:
                    content += citation

            return content
        except Exception as e:
            logger.error(f"Error invoking Ollama model '{self.model}': {e}", exc_info=True)
            return f"⚠️ LLM Error: Unable to generate response ({type(e).__name__})."

    async def list_available_models(self) -> List[str]:
        """List local models available in Ollama."""
        try:
            res = await self.client.list()
            models = [m.get("name", m.get("model", "")) for m in res.get("models", [])]
            return models
        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return [self.model]
