from dataclasses import dataclass
from typing import Generic, TypeVar, Callable, Any, Union
from abc import ABC, abstractmethod

T = TypeVar("T")  # The type of the Success value
E = TypeVar("E")  # The type of the Error value
U = TypeVar("U")  # The type for mapped values

class Result(ABC, Generic[T, E]):
    """Abstract base class for Result."""
    @abstractmethod
    def map(self, func: Callable[[T], U]) -> 'Result[U, E]':
        pass
    @abstractmethod
    def unwrap(self) -> T:
        """Extracts the value or raises an error."""
        pass
    @abstractmethod
    def and_then(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        pass

@dataclass(frozen=True)
class Ok(Result[T, E]):
    value: T

    def map(self, func: Callable[[T], U]) -> 'Ok[U, E]':
        return Ok(func(self.value))

    def unwrap(self) -> T:
        return self.value
    
    def and_then(self, func: Callable[[T], 'Result[U, E]']) -> 'Result[U, E]':
        return func(self.value)

@dataclass(frozen=True)
class Err(Result[T, E]):
    error: E

    def map(self, func: Callable[[Any], Any]) -> 'Err[T, E]':
        return self  # Short-circuit: skip mapping on failure

    def unwrap(self) -> T:
        raise ValueError(f"Called unwrap on an Error: {self.error}")
    
    def and_then(self, func: Callable[[Any], Any]) -> 'Err[T, E]':
        return self
