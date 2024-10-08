# directory_tree.py
# TODO: move button implementation to main.py
import os
import tkinter as tk
from tkinter import ttk

class DirectoryTree:
    def __init__(self, main_frame):
        """Initialize the DirectoryTree class."""
        self.main_frame = main_frame
        self.save_directory = os.path.dirname(os.path.abspath(__file__))
        parent_directory = os.path.dirname(self.save_directory)
        self.history = [parent_directory, self.save_directory]
        self.current_index = 1  # Start at index 1, which is the save_directory

        self.create_directory_view()

    def create_directory_view(self):
        # Create frame for navigation buttons
        nav_frame = ttk.Frame(self.main_frame)
        nav_frame.grid(row=2, column=0, columnspan=2, pady=(5, 0), sticky="w")

        # Back button
        self.back_button = ttk.Button(nav_frame, text="Back", command=self.go_back)
        self.back_button.pack(side='left', padx=(0, 5))

        # Current path label
        self.path_label = ttk.Label(nav_frame, text=self.save_directory)
        self.path_label.pack(side='left', fill='x', expand=True)

        # Frame for the directory listbox and scrollbar
        dir_frame = ttk.Frame(self.main_frame)
        dir_frame.grid(row=3, column=0, columnspan=2, pady=(5, 0), sticky="nsew")

        # Listbox to display directories and files
        self.dir_listbox = tk.Listbox(dir_frame, selectmode='browse', activestyle='none')
        self.dir_listbox.pack(side='left', fill='both', expand=True)

        # Scrollbar for the directory listbox
        scrollbar = ttk.Scrollbar(dir_frame, orient="vertical", command=self.dir_listbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.dir_listbox.configure(yscrollcommand=scrollbar.set)

        # Bind double-click event
        self.dir_listbox.bind('<Double-1>', self.on_item_select)
        self.dir_listbox.bind('<<ListboxSelect>>', self.on_selection_change)

        self.populate_listbox()

    def populate_listbox(self):
        self.dir_listbox.delete(0, tk.END)
        try:
            items = os.listdir(self.save_directory)
            # Custom sorting function
            def sort_key(item):
                import re
                return [int(c) if c.isdigit() else c.lower() for c in re.split(r'(\d+)', item)]
            
            sorted_items = sorted(items, key=sort_key)
            for item in sorted_items:
                full_path = os.path.join(self.save_directory, item)
                if os.path.isdir(full_path):
                    self.dir_listbox.insert(tk.END, f"> {item}")
                    self.dir_listbox.itemconfig(tk.END, fg='blue')  # Directories in blue
                else:
                    self.dir_listbox.insert(tk.END, item)
                    self.dir_listbox.itemconfig(tk.END, fg='black')  # Files in black
        except PermissionError:
            print(f"Permission denied: {self.save_directory}")
        except FileNotFoundError:
            print(f"Directory not found: {self.save_directory}")

    def on_item_select(self, event):
        selection = self.dir_listbox.curselection()
        if selection:
            item = self.dir_listbox.get(selection[0])
            full_path = os.path.join(self.save_directory, item)
            if os.path.isdir(full_path):
                self.save_directory = full_path
                self.history = self.history[:self.current_index + 1]
                self.history.append(self.save_directory)
                self.current_index += 1
                self.populate_listbox()
                self.update_path_label()
                self.dir_listbox.event_generate("<<DirectorySelected>>")
                
                # Update back button state
                self.back_button.state(['!disabled'])
                
                # Print when moving to a new directory
                print(f"Moved to directory: {self.save_directory}")

    def on_selection_change(self, event):
        selection = self.dir_listbox.curselection()
        if selection:
            item = self.dir_listbox.get(selection[0])
            full_path = os.path.join(self.save_directory, item)
            if not os.path.isdir(full_path):
                self.dir_listbox.selection_clear(0, tk.END)

    def go_back(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.save_directory = self.history[self.current_index]
            self.populate_listbox()
            self.update_path_label()
            self.dir_listbox.event_generate("<<DirectorySelected>>")
        
            # Update back button state
            self.back_button.state(['!disabled'] if self.current_index > 0 else ['disabled'])
            
            # Print when moving back to a previous directory
            print(f"Moved back to directory: {self.save_directory}")

    def update_path_label(self):
        self.path_label.config(text=self.save_directory)

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
        # Generate the custom event
        self.dir_tree.event_generate("<<DirectorySelected>>", when="tail")

    def on_item_open(self, event):
        """Handle the event when a directory or file is clicked/opened."""
        selected_items = self.dir_tree.selection()
        if selected_items:
            selected_item = selected_items[0]
            full_path = self.dir_tree.item(selected_item, 'values')[0]
            print(f"Item opened: {full_path}")  # Debug statement or handle the event as needed

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

        # Set the initial save directory to the script's directory
        self.save_directory = initial_path

        return dir_tree, dir_frame

    def update_directory_selection(self, event):
        """Update the save directory and generate a custom event."""
        selected_item = self.dir_tree.selection()
        if selected_item:
            # Get the full path of the selected item
            self.save_directory = self.dir_tree.item(selected_item, 'values')[0]

            # Generate the custom event with the selected directory
            self.dir_tree.event_generate("<<DirectorySelected>>")

        print("Save directory selected:", self.save_directory)  # Debug statement
