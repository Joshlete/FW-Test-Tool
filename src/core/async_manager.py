"""
Async Manager for Tab Components

This module provides async infrastructure including event loops, thread pool executors,
and utility methods for running async operations in tabs.
"""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Any, Coroutine


class AsyncManager:
    """
    Manages async infrastructure for tabs including event loops, executors,
    and utility methods for safe async operations.
    """
    
    def __init__(self, max_workers: int = 2):
        """
        Initialize the AsyncManager.
        
        Args:
            max_workers: Maximum number of worker threads for the executor
        """
        self.max_workers = max_workers
        
        # Initialize async infrastructure
        self.loop = None
        self.executor = None
        self.async_thread = None
        
        # Start the async infrastructure
        self._initialize_async()
    
    def _initialize_async(self) -> None:
        """Initialize the async loop and executor."""
        # Create new event loop (but don't set it as current loop yet)
        self.loop = asyncio.new_event_loop()
        
        # Create thread pool executor
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # Start the async thread - it will set its own loop
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
    
    def _run_async_loop(self) -> None:
        """Run the asyncio event loop in a separate thread."""
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()
    
    def cleanup(self) -> None:
        """Clean up async resources in proper order."""
        print(f"AsyncManager: Starting cleanup")
        
        # 1. Stop the event loop first
        if self.loop and not self.loop.is_closed():
            print(f"AsyncManager: Stopping event loop")
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                # Loop might already be stopped
                pass
        
        # 2. Wait for async thread to finish
        if self.async_thread and self.async_thread.is_alive():
            print(f"AsyncManager: Waiting for async thread to finish")
            self.async_thread.join(timeout=3)  # Increased timeout
            if self.async_thread.is_alive():
                print(f"AsyncManager: Warning - async thread still alive after timeout")
        
        # 3. Shutdown executor after loop is stopped
        if self.executor:
            print(f"AsyncManager: Shutting down executor")
            self.executor.shutdown(wait=True)  # Wait for tasks to complete
        
        print(f"AsyncManager: Cleanup complete")
    
    def run_async(self, coro: Coroutine) -> Optional[Any]:
        """
        Run a coroutine in the async loop.
        
        Args:
            coro: Coroutine to run
            
        Returns:
            Future object
            
        Raises:
            RuntimeError: If async infrastructure is not available
        """
        if not self.is_available():
            raise RuntimeError("AsyncManager is not available - may be uninitialized or cleaned up")
        
        try:
            return asyncio.run_coroutine_threadsafe(coro, self.loop)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to run coroutine: {e}")
    
    async def run_in_executor(self, func: Callable, *args) -> Any:
        """
        Run a blocking function in the thread pool executor.
        
        Args:
            func: Function to run
            *args: Arguments to pass to the function
            
        Returns:
            Result of the function
            
        Raises:
            RuntimeError: If executor is not available
        """
        if not self.executor:
            raise RuntimeError("Executor not available")
        return await self.loop.run_in_executor(self.executor, lambda: func(*args))
    
    
    def is_available(self) -> bool:
        """Check if the async infrastructure is available and running."""
        return (self.loop is not None and 
                not self.loop.is_closed() and
                self.executor is not None and 
                not self.executor._shutdown and
                self.async_thread is not None and 
                self.async_thread.is_alive())
