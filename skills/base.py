"""
tokudo.skills.base
Abstract Base Class for Tokudo Skills and Dynamic Hot-Reloading Registry.
"""

from __future__ import annotations
import ast
import inspect
import importlib
import importlib.util
import logging
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Type

logger = logging.getLogger("tokudo.skills")


class BaseSkill(ABC):
    """
    Abstract base class for all Tokudo skills.
    Each skill exposes a name, description, parameters schema,
    and whether it requires Human-In-The-Loop approval.
    """
    name: str = "base_skill"
    description: str = "Base skill description"
    parameters: Dict[str, Any] = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval: bool = False

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Executes the skill action with given keyword arguments."""
        pass

    def to_openai_tool(self) -> Dict[str, Any]:
        """Converts skill definition to OpenAI/Gemini function calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class SkillRegistry:
    """
    Central registry for dynamic skill discovery, tool-calling registration,
    and runtime Hot-Reloading without server restarts.
    """

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or (Path(__file__).parent)
        self.skills: Dict[str, BaseSkill] = {}
        self._loaded_modules: Dict[str, Any] = {}

    def discover_and_load(self) -> None:
        """Discovers and instantiates all BaseSkill subclasses from the skills directory."""
        logger.info(f"Scanning skills directory: {self.skills_dir}")
        directories = [self.skills_dir]
        local_dir = Path.cwd() / "skills"
        if local_dir.resolve() != self.skills_dir.resolve() and local_dir.exists():
            directories.append(local_dir)

        for d in directories:
            for py_file in d.glob("*.py"):
                if py_file.name.startswith("__") or py_file.name == "base.py":
                    continue
                self._load_module_from_file(py_file)

        logger.info(f"Loaded {len(self.skills)} skills: {list(self.skills.keys())}")

    def _load_module_from_file(self, file_path: Path) -> None:
        """Dynamically loads or reloads a Python module and registers any BaseSkill classes."""
        module_name = f"skills.{file_path.stem}"
        try:
            if module_name in sys.modules:
                module = importlib.reload(sys.modules[module_name])
            else:
                spec = importlib.util.spec_from_file_location(module_name, file_path)
                if spec is None or spec.loader is None:
                    return
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)

            self._loaded_modules[module_name] = module

            # Scan module classes
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                    instance = obj()
                    self.skills[instance.name] = instance
                    logger.info(f"Registered skill: '{instance.name}' (Approval: {instance.requires_approval})")
        except Exception as e:
            logger.error(f"Failed to load skill module {file_path.name}: {e}", exc_info=True)

    def hot_reload(self, target_file_name: Optional[str] = None) -> List[str]:
        """
        Hot-reloads a specific skill file or all skills dynamically.
        Enables Self-Expanding skill writing in real-time.
        """
        if target_file_name:
            target_path = self.skills_dir / target_file_name
            if not target_path.exists():
                raise FileNotFoundError(f"Skill file not found: {target_file_name}")
            self._load_module_from_file(target_path)
        else:
            self.discover_and_load()

        return list(self.skills.keys())

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        return self.skills.get(name)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Returns list of all registered tool schemas formatted for LLM Function Calling."""
        return [skill.to_openai_tool() for skill in self.skills.values()]

    async def execute(self, skill_name: str, arguments: Dict[str, Any]) -> Any:
        skill = self.get_skill(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' not found in registry.")
        return await skill.execute(**arguments)
