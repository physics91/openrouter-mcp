"""
Lifecycle Manager for Collective Intelligence Components

This module provides singleton lifecycle management for collective intelligence
components to prevent resource leaks from background tasks and ensure proper
cleanup on server shutdown.

Key Features:
- Lazy initialization of singleton instances
- Automatic cleanup task management
- Graceful shutdown of all components
- Thread-safe singleton creation
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, TypeVar, cast

from .adaptive_router import AdaptiveRouter
from .base import ModelProvider
from .collaborative_solver import CollaborativeSolver
from .consensus_engine import ConsensusConfig, ConsensusEngine
from .cross_validator import CrossValidator
from .ensemble_reasoning import EnsembleReasoner
from .operational_controls import OperationalConfig

T = TypeVar("T")

logger = logging.getLogger(__name__)


class CollectiveIntelligenceLifecycleManager:
    """
    Manages lifecycle of collective intelligence components as singletons.

    This class ensures:
    1. Only one instance of each component exists (singleton pattern)
    2. Components are lazily initialized on first use
    3. All background tasks are properly cleaned up on shutdown
    4. Thread-safe initialization with asyncio.Lock
    """

    def __init__(self) -> None:
        self._consensus_engine: Optional[ConsensusEngine] = None
        self._collaborative_solver: Optional[CollaborativeSolver] = None
        self._ensemble_reasoner: Optional[EnsembleReasoner] = None
        self._adaptive_router: Optional[AdaptiveRouter] = None
        self._cross_validator: Optional[CrossValidator] = None

        self._model_provider: Optional[ModelProvider] = None
        self._operational_config: Optional[OperationalConfig] = None

        # Lock for thread-safe singleton initialization
        self._init_lock = asyncio.Lock()
        self._shutdown_event = asyncio.Event()
        self._is_shutdown = False

        logger.info("CollectiveIntelligenceLifecycleManager initialized")

    def configure(
        self,
        model_provider: ModelProvider,
        operational_config: Optional[OperationalConfig] = None,
    ) -> None:
        """
        Configure the lifecycle manager with required dependencies.

        Args:
            model_provider: ModelProvider instance for components
            operational_config: Optional operational configuration (defaults to conservative)
        """
        self._model_provider = model_provider
        self._operational_config = operational_config or OperationalConfig.conservative()
        logger.info("CollectiveIntelligenceLifecycleManager configured")

    def _require_model_provider(self) -> ModelProvider:
        """Return the configured provider or reject component access."""
        if self._model_provider is None:
            raise RuntimeError("LifecycleManager not configured. Call configure() first.")
        return self._model_provider

    async def _get_or_create_component(
        self,
        attr_name: str,
        factory: Callable[[], T],
        component_name: str,
    ) -> T:
        """Get or create a singleton component by attribute name."""
        if self._is_shutdown:
            raise RuntimeError("LifecycleManager is shutdown, cannot create instances")
        if self._model_provider is None:
            raise RuntimeError("LifecycleManager not configured. Call configure() first.")

        async with self._init_lock:
            instance = getattr(self, attr_name)
            if instance is None:
                logger.info(f"Creating singleton {component_name} instance")
                instance = factory()
                setattr(self, attr_name, instance)
                logger.info(f"{component_name} singleton created")
            return cast(T, instance)

    async def get_consensus_engine(
        self, config: Optional[ConsensusConfig] = None
    ) -> ConsensusEngine:
        """Get or create singleton ConsensusEngine instance."""
        provider = self._require_model_provider()

        def factory() -> ConsensusEngine:
            cfg = config if config is not None else ConsensusConfig()
            cfg.operational_config = self._operational_config
            return ConsensusEngine(provider, cfg)

        return await self._get_or_create_component("_consensus_engine", factory, "ConsensusEngine")

    async def get_collaborative_solver(self) -> CollaborativeSolver:
        """Get or create singleton CollaborativeSolver instance."""
        provider = self._require_model_provider()
        operational_config = self._operational_config
        return await self._get_or_create_component(
            "_collaborative_solver",
            lambda: CollaborativeSolver(provider, operational_config),
            "CollaborativeSolver",
        )

    async def get_ensemble_reasoner(self) -> EnsembleReasoner:
        """Get or create singleton EnsembleReasoner instance."""
        provider = self._require_model_provider()
        return await self._get_or_create_component(
            "_ensemble_reasoner",
            lambda: EnsembleReasoner(provider),
            "EnsembleReasoner",
        )

    async def get_adaptive_router(self) -> AdaptiveRouter:
        """Get or create singleton AdaptiveRouter instance."""
        provider = self._require_model_provider()
        return await self._get_or_create_component(
            "_adaptive_router",
            lambda: AdaptiveRouter(provider),
            "AdaptiveRouter",
        )

    async def get_cross_validator(self) -> CrossValidator:
        """Get or create singleton CrossValidator instance."""
        provider = self._require_model_provider()
        return await self._get_or_create_component(
            "_cross_validator",
            lambda: CrossValidator(provider),
            "CrossValidator",
        )

    def _collect_shutdown_tasks(self) -> list[tuple[str, Awaitable[Any]]]:
        """Collect named component shutdown tasks in lifecycle order."""
        shutdown_tasks: list[tuple[str, Awaitable[Any]]] = []

        if self._consensus_engine is not None:
            logger.info("Shutting down ConsensusEngine...")
            shutdown_tasks.append(
                ("ConsensusEngine", self._consensus_engine.shutdown())
            )

        if self._collaborative_solver is not None:
            logger.info("Shutting down CollaborativeSolver...")
            shutdown_tasks.append(
                ("CollaborativeSolver", self._collaborative_solver.shutdown())
            )

        if self._ensemble_reasoner is not None:
            logger.info("Shutting down EnsembleReasoner...")
            if hasattr(self._ensemble_reasoner, "shutdown"):
                shutdown_tasks.append(
                    ("EnsembleReasoner", self._ensemble_reasoner.shutdown())
                )

        if self._adaptive_router is not None:
            logger.info("Shutting down AdaptiveRouter...")
            if hasattr(self._adaptive_router, "shutdown"):
                shutdown_tasks.append(
                    ("AdaptiveRouter", self._adaptive_router.shutdown())
                )

        if self._cross_validator is not None:
            logger.info("Shutting down CrossValidator...")
            if hasattr(self._cross_validator, "shutdown"):
                shutdown_tasks.append(
                    ("CrossValidator", self._cross_validator.shutdown())
                )

        return shutdown_tasks

    @staticmethod
    def _log_shutdown_failures(
        shutdown_tasks: list[tuple[str, Awaitable[Any]]],
        results: list[Any],
    ) -> None:
        """Report component shutdown failures without stopping sibling cleanup."""
        for (component_name, _), result in zip(shutdown_tasks, results):
            if isinstance(result, asyncio.CancelledError):
                logger.warning(f"Component {component_name} shutdown was cancelled")
            elif isinstance(result, Exception):
                logger.error(f"Component {component_name} shutdown failed: {result}")
            elif isinstance(result, BaseException):
                logger.critical(f"Component {component_name} shutdown failed: {result}")

    async def shutdown(self) -> None:
        """
        Gracefully shutdown all collective intelligence components.

        This method:
        1. Marks the manager as shutdown (prevents new instance creation)
        2. Shuts down each component if it was created
        3. Cancels all background cleanup tasks
        4. Waits for tasks to complete gracefully
        """
        if self._is_shutdown:
            logger.warning("LifecycleManager already shutdown")
            return

        logger.info("Shutting down CollectiveIntelligenceLifecycleManager...")
        self._is_shutdown = True
        self._shutdown_event.set()

        # Shutdown all created components
        shutdown_tasks = self._collect_shutdown_tasks()

        # Execute all shutdown tasks
        if shutdown_tasks:
            results = await asyncio.gather(
                *(task for _, task in shutdown_tasks),
                return_exceptions=True,
            )
            self._log_shutdown_failures(shutdown_tasks, results)

        logger.info("CollectiveIntelligenceLifecycleManager shutdown complete")

    def is_shutdown(self) -> bool:
        """Check if manager has been shutdown."""
        return self._is_shutdown

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator["CollectiveIntelligenceLifecycleManager"]:
        """
        Context manager for managing lifecycle.

        Usage:
            async with lifecycle_manager.lifespan():
                # Use components
                pass
            # Components automatically shutdown
        """
        try:
            yield self
        finally:
            await self.shutdown()


# Global singleton instance
_lifecycle_manager: Optional[CollectiveIntelligenceLifecycleManager] = None
_manager_lock: Optional[asyncio.Lock] = None


def _get_manager_lock() -> asyncio.Lock:
    global _manager_lock
    if _manager_lock is None:
        _manager_lock = asyncio.Lock()
    return _manager_lock


async def get_lifecycle_manager() -> CollectiveIntelligenceLifecycleManager:
    """
    Get the global singleton lifecycle manager.

    Returns:
        CollectiveIntelligenceLifecycleManager instance
    """
    global _lifecycle_manager

    if _lifecycle_manager is None:
        async with _get_manager_lock():
            if _lifecycle_manager is None:
                _lifecycle_manager = CollectiveIntelligenceLifecycleManager()

    return _lifecycle_manager


async def shutdown_lifecycle_manager() -> None:
    """
    Shutdown the global lifecycle manager.

    This should be called on server shutdown to ensure all
    background tasks are properly cleaned up.
    """
    global _lifecycle_manager

    if _lifecycle_manager is not None:
        await _lifecycle_manager.shutdown()
        _lifecycle_manager = None
