# directory_tree.py

import os
import tkinter as tk
from tkinter import ttk

class DirectoryTree:
    def __init__(self, main_frame):
        """Initialize the DirectoryTree class."""
        self.main_frame = main_frame
        self.save_directory = ""  # Instance variable to store the selected directory

        # Create the directory tree UI components
        self.dir_tree, self.dir_frame = self.create_directory_tree()

    def get_directory(self):
        """Return the currently selected directory."""
        return self.save_directory

    def populate_tree(self, tree, parent, path):
        """Recursively populate the tree with directories and subdirectories, handling permission errors."""
        try:
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    # Add the directory to the tree
                    node = tree.insert(parent, 'end', text=entry, open=False, values=[full_path])
                    # Recursively populate the tree with the contents of the directory
                    self.populate_tree(tree, node, full_path)
        except PermissionError:
            print(f"Permission denied: {path}")  # Feedback for debugging or logging
        except FileNotFoundError:
            print(f"Directory not found: {path}")  # Handle directory not found

    def on_directory_select(self, event):
        """Update the save directory when a directory is selected."""
        selected_items = self.dir_tree.selection()

        if not selected_items:
            self.dir_label.config(text="No directory selected.")
            return  # Return early if no item is selected

        selected_item = selected_items[0]
        self.save_directory = self.dir_tree.item(selected_item, 'values')[0]
        self.dir_label.config(text=f"Save Directory: {self.save_directory}")

    def create_directory_tree(self):
        """Create and set up the directory tree view with a scrollbar."""
        # Frame for the directory tree and scrollbar
        dir_frame = ttk.Frame(self.main_frame)
        dir_frame.grid(row=2, column=0, columnspan=2, pady=(5, 0), sticky="w")

        # Treeview to display directories
        dir_tree = ttk.Treeview(dir_frame, columns=('fullpath',), selectmode='browse')
        dir_tree.heading('#0', text='Directory Tree', anchor='w')
        dir_tree.column('#0', stretch=True)
        dir_tree.pack(side='left', fill='both', expand=True)

        # Scrollbar for the directory tree
        scrollbar = ttk.Scrollbar(dir_frame, orient="vertical", command=dir_tree.yview)
        scrollbar.pack(side='right', fill='y')
        dir_tree.configure(yscrollcommand=scrollbar.set)

        # Populate tree with initial directory (script's directory)
        initial_path = os.path.dirname(os.path.abspath(__file__))  # Set initial path to the script's directory
        root_node = dir_tree.insert('', 'end', text=os.path.basename(initial_path), open=True, values=[initial_path])
        self.populate_tree(dir_tree, root_node, initial_path)

        # Bind the selection event
        dir_tree.bind('<<TreeviewSelect>>', self.on_directory_select)

        # Label to display selected directory
        self.dir_label = ttk.Label(self.main_frame, text=f"Save Directory: {initial_path}")
        self.dir_label.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky="w")

        # Set the initial save directory to the script's directory
        self.save_directory = initial_path

        return dir_tree, dir_frame

    def update_directory_selection(self, event):
        """Update the save directory based on the selected item in the directory tree."""
        selected_item = self.dir_tree.selection()
        if selected_item:
            # Get the path relative to the current working directory
            selected_path = self.dir_tree.item(selected_item)['text']

            # Normalize the path relative to the current directory
            if selected_path == "." or selected_path == "./" or selected_path == os.path.basename(os.getcwd()):
                self.save_directory = os.getcwd()  # Use the current working directory path
            else:
                self.save_directory = os.path.relpath(selected_path, start=os.getcwd())  # Ensure it's a relative path
            
            self.dir_label.config(text=f"Save Directory: {self.save_directory}")
            print("Save directory selected:", self.save_directory)  # Debug statement
