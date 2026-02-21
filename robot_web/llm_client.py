"""
Pluggable LLM client voor robot aansturing.

Backends: local (Ollama), openai, anthropic.
Ondersteunt tool/function calling voor robot acties.
"""

import json
from typing import Optional

import httpx


# Robot tools die de LLM kan aanroepen
ROBOT_TOOLS = [
    {
        "name": "navigate_to",
        "description": "Navigeer de robot naar een locatie. Gebruik een naam (bijv. 'keuken') of coördinaten.",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "Naam van de locatie (bijv. 'keuken', 'slaapkamer') of 'x,y' coördinaten"
                }
            },
            "required": ["location"]
        }
    },
    {
        "name": "stop",
        "description": "Stop de robot en annuleer huidige navigatie.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "look_around",
        "description": "Draai de robot 360 graden om de omgeving te bekijken.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "describe_scene",
        "description": "Beschrijf wat de camera ziet.",
        "parameters": {"type": "object", "properties": {}}
    },
]


class LLMClient:
    """Pluggable LLM client."""

    def __init__(self, config: dict):
        self.backend = config.get('backend', 'local')
        self.model = config.get('model', 'llama3.2')
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.api_key = config.get('api_key', '')
        self.system_prompt = config.get('system_prompt', 'Je bestuurt een robot.')

        self.conversation: list[dict] = []
        self._http = httpx.AsyncClient(timeout=60.0)

    async def chat(self, message: str, waypoints: dict = None) -> dict:
        """
        Stuur bericht naar LLM, krijg response + eventuele tool calls terug.

        Returns: {
            "response": "tekst antwoord",
            "actions": [{"tool": "navigate_to", "args": {"location": "keuken"}}]
        }
        """
        # Voeg waypoint info toe aan systeem context
        system = self.system_prompt
        if waypoints:
            locations = ", ".join(waypoints.keys())
            system += f"\n\nBekende locaties: {locations}"

        self.conversation.append({"role": "user", "content": message})

        if self.backend == 'local':
            result = await self._chat_ollama(system)
        elif self.backend == 'openai':
            result = await self._chat_openai(system)
        elif self.backend == 'anthropic':
            result = await self._chat_anthropic(system)
        else:
            result = {"response": f"Onbekend backend: {self.backend}", "actions": []}

        self.conversation.append({"role": "assistant", "content": result["response"]})
        return result

    async def _chat_ollama(self, system: str) -> dict:
        """Chat via Ollama API (lokaal)."""
        messages = [{"role": "system", "content": system}] + self.conversation

        try:
            resp = await self._http.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "tools": self._format_tools_openai(),
                }
            )
            resp.raise_for_status()
            data = resp.json()

            content = data.get("message", {}).get("content", "")
            tool_calls = data.get("message", {}).get("tool_calls", [])

            actions = []
            for tc in tool_calls:
                actions.append({
                    "tool": tc["function"]["name"],
                    "args": tc["function"].get("arguments", {}),
                })

            return {"response": content, "actions": actions}

        except Exception as e:
            return {"response": f"LLM fout: {e}", "actions": []}

    async def _chat_openai(self, system: str) -> dict:
        """Chat via OpenAI-compatible API."""
        messages = [{"role": "system", "content": system}] + self.conversation

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            resp = await self._http.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "tools": self._format_tools_openai(),
                }
            )
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]["message"]
            content = choice.get("content", "")
            tool_calls = choice.get("tool_calls", [])

            actions = []
            for tc in tool_calls:
                args = tc["function"].get("arguments", "{}")
                if isinstance(args, str):
                    args = json.loads(args)
                actions.append({
                    "tool": tc["function"]["name"],
                    "args": args,
                })

            return {"response": content, "actions": actions}

        except Exception as e:
            return {"response": f"LLM fout: {e}", "actions": []}

    async def _chat_anthropic(self, system: str) -> dict:
        """Chat via Anthropic API."""
        messages = self.conversation.copy()

        try:
            resp = await self._http.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": self.model,
                    "max_tokens": 1024,
                    "system": system,
                    "messages": messages,
                    "tools": self._format_tools_anthropic(),
                }
            )
            resp.raise_for_status()
            data = resp.json()

            content = ""
            actions = []
            for block in data.get("content", []):
                if block["type"] == "text":
                    content += block["text"]
                elif block["type"] == "tool_use":
                    actions.append({
                        "tool": block["name"],
                        "args": block.get("input", {}),
                    })

            return {"response": content, "actions": actions}

        except Exception as e:
            return {"response": f"LLM fout: {e}", "actions": []}

    def _format_tools_openai(self) -> list:
        """Format tools voor OpenAI/Ollama API."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["parameters"],
                }
            }
            for t in ROBOT_TOOLS
        ]

    def _format_tools_anthropic(self) -> list:
        """Format tools voor Anthropic API."""
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"],
            }
            for t in ROBOT_TOOLS
        ]

    def clear_conversation(self):
        """Wis conversatie geschiedenis."""
        self.conversation = []

    async def close(self):
        """Sluit HTTP client."""
        await self._http.aclose()
