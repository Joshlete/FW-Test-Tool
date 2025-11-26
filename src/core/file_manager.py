"""
File Manager for Application Components

This module provides file management functionality including safe file paths,
step-based naming, and support for various file formats (JSON, images, text).
"""
import os
import json
from typing import Tuple, Optional, Any, Union
from PIL import Image


class FileManager:
    """
    Handles file operations with step-based naming, safe paths, and format support.
    """
    
    def __init__(self, default_directory: str = ".", step_manager=None, notification_manager=None, debug: bool = False):
        """
        Initialize the FileManager.
        
        Args:
            default_directory: Default directory for file operations
            step_manager: StepManager instance for step prefix generation
            notification_manager: NotificationManager for user feedback
            debug: Enable debug logging
        """
        self.default_directory = default_directory
        self.step_manager = step_manager
        self.notification_manager = notification_manager
        self.debug = debug
        
        # Track directory change callbacks for automatic sync
        self._directory_change_callbacks = []
    
    def set_default_directory(self, directory: str) -> None:
        """Set the default directory for file operations."""
        old_directory = self.default_directory
        self.default_directory = directory
        
        if self.debug and old_directory != directory:
            print(f"FileManager: Directory changed from {old_directory} to {directory}")
    
    def register_directory_change_callback(self, callback):
        """Register a callback to be notified of directory changes."""
        self._directory_change_callbacks.append(callback)
    
    def connect_to_app_directory_changes(self, app):
        """Connect to app's directory change system for automatic sync."""
        app.register_directory_callback(self.set_default_directory)
    
    def get_safe_filepath(self, directory: Optional[str], base_filename: str, 
                         extension: str = ".json", step_number: Optional[int] = None) -> Tuple[str, str]:
        """
        Creates a safe filepath that won't overwrite existing files.
        
        Args:
            directory: Directory to save the file in (uses default if None)
            base_filename: Base name for the file (without step prefix)
            extension: File extension including the dot (default: .json)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            A tuple of (safe_filepath, filename_used)
        """
        if directory is None:
            directory = self.default_directory
            
        # Get step prefix from step manager if available
        step_prefix = ""
        if self.step_manager:
            if step_number is not None:
                try:
                    step_prefix = self.step_manager.get_step_prefix(step_number)
                except (ValueError, AttributeError):
                    step_prefix = self.step_manager.get_step_prefix()  # Fall back to current step
            else:
                step_prefix = self.step_manager.get_step_prefix()
        
        # Add step prefix to filename
        prefixed_filename = f"{step_prefix}{base_filename}"
        
        # Clean up filename - remove invalid characters
        clean_filename = ''.join(c for c in prefixed_filename if c.isalnum() or c in '._- ')
        
        # Create initial filepath
        filepath = os.path.join(directory, f"{clean_filename}{extension}")
        filename = f"{clean_filename}{extension}"
        
        # If file exists, add a counter to make it unique
        counter = 1
        while os.path.exists(filepath):
            counter_filename = f"{clean_filename} ({counter}){extension}"
            filepath = os.path.join(directory, counter_filename)
            filename = counter_filename
            counter += 1
        
        return filepath, filename
    
    def save_json_data(self, data: Union[dict, str], base_filename: str, 
                      directory: Optional[str] = None, step_number: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Saves JSON data to a file with step prefix and no overwriting.
        
        Args:
            data: The JSON data to save (dict or JSON string)
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses default if None)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.default_directory
        
        try:
            # Convert string to dict if needed
            if isinstance(data, str):
                try:
                    data_dict = json.loads(data)
                except json.JSONDecodeError:
                    # If not valid JSON, save as text file instead
                    return self.save_text_data(data, base_filename, directory, ".json", step_number)
            else:
                data_dict = data
            
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, ".json", step_number)
            
            # Write with pretty formatting, prefixing each line with a single tab
            pretty_json = json.dumps(data_dict, indent=4, ensure_ascii=False)
            # Ensure consistent trailing newline handling before prefixing
            if not pretty_json.endswith('\n'):
                pretty_json = pretty_json + '\n'
            tab_prefixed_json = '\t' + pretty_json.replace('\n', '\n\t')
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(tab_prefixed_json)
            
            if self.debug:
                print(f"JSON saved to: {filepath}")
            
            if self.notification_manager:
                self.notification_manager.show_success(f"File Saved: {filename}")
            
            return True, filepath
        except Exception as e:
            if self.debug:
                print(f"Error saving JSON: {str(e)}")
            
            if self.notification_manager:
                self.notification_manager.show_error(f"File Save Failed: {str(e)}")
            
            return False, None
    
    def save_image_data(self, image_data: Union[bytes, Image.Image], base_filename: str,
                       directory: Optional[str] = None, format: str = 'PNG', 
                       step_number: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Saves image data to a file with step prefix and no overwriting.
        
        Args:
            image_data: The image data (bytes or PIL Image)
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses default if None)
            format: Image format (default: 'PNG')
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.default_directory
        
        extension = f".{format.lower()}"
        
        try:
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, extension, step_number)
            
            # Handle different image data types
            if isinstance(image_data, bytes):
                with open(filepath, 'wb') as file:
                    file.write(image_data)
            else:
                # Assume PIL Image
                image_data.save(filepath, format=format)
            
            if self.debug:   
                print(f"Image saved to: {filepath}")

            if self.notification_manager:
                self.notification_manager.show_success(f"File Saved: {filename}")
            
            return True, filepath
        except Exception as e:
            if self.debug:
                print(f"Error saving image: {str(e)}")
            
            if self.notification_manager:
                self.notification_manager.show_error(f"File Save Failed: {str(e)}")
            
            return False, None
    
    def save_text_data(self, text_data: str, base_filename: str, 
                      directory: Optional[str] = None, extension: str = ".txt", 
                      step_number: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Saves text data to a file with step prefix and no overwriting.
        
        Args:
            text_data: The text data to save
            base_filename: Base name for the file without step prefix or extension
            directory: Directory to save to (uses default if None)
            extension: File extension (default: .txt)
            step_number: Explicit step number to use, or None to use current
            
        Returns:
            tuple: (success, filepath)
        """
        if directory is None:
            directory = self.default_directory
        
        try:
            # Get safe filepath
            filepath, filename = self.get_safe_filepath(directory, base_filename, extension, step_number)
            
            # Write text data
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(text_data)
            
            if self.debug:
                print(f"Text saved to: {filepath}")
            
            if self.notification_manager:
                self.notification_manager.show_success(f"File Saved: {filename}")
            
            return True, filepath
        except Exception as e:
            if self.debug:
                print(f"Error saving text: {str(e)}")
            
            if self.notification_manager:
                self.notification_manager.show_error(f"File Save Failed: {str(e)}")
            
            return False, None
    
    def ensure_directory_exists(self, directory: str) -> bool:
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory: Directory path to ensure exists
            
        Returns:
            True if directory exists or was created successfully
        """
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except Exception as e:
            if self.debug:
                print(f"Error creating directory {directory}: {str(e)}")
            
            if self.notification_manager:
                self.notification_manager.show_error(f"Directory creation failed: {str(e)}")
            
            return False
    
    def get_file_size(self, filepath: str) -> Optional[int]:
        """
        Get the size of a file in bytes.
        
        Args:
            filepath: Path to the file
            
        Returns:
            File size in bytes, or None if file doesn't exist
        """
        try:
            return os.path.getsize(filepath)
        except (OSError, FileNotFoundError):
            return None
    
    def file_exists(self, filepath: str) -> bool:
        """
        Check if a file exists.
        
        Args:
            filepath: Path to check
            
        Returns:
            True if file exists
        """
        return os.path.exists(filepath)
