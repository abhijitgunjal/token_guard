from typing import Any, Callable, Dict, Type, Union

from token_guard.policies.base import AsyncBasePolicy, BasePolicy

PolicyType = Union[Type[BasePolicy], Type[AsyncBasePolicy], Callable[..., Union[BasePolicy, AsyncBasePolicy]]]


class PolicyFactory:
    _registry: Dict[str, PolicyType] = {}

    @classmethod
    def register(cls, name: str, policy_cls_or_builder: PolicyType) -> None:
        """Register a policy class or builder function under a given string key."""
        cls._registry[name.lower()] = policy_cls_or_builder

    @classmethod
    def create(cls, name: str, **kwargs: Any) -> Union[BasePolicy, AsyncBasePolicy]:
        """Create and return an instance of a registered policy."""
        key = name.lower()
        if key not in cls._registry:
            valid = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(f"Unknown policy '{name}'. Available policies: [{valid}]")

        builder = cls._registry[key]
        return builder(**kwargs)

    @classmethod
    def list_policies(cls) -> list[str]:
        """List all registered policy names."""
        return sorted(list(cls._registry.keys()))
