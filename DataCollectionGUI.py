"""
Original script by Connor Browne for his 2023 thesis:
"Evaluating the Effectiveness of Preprocessing Methods on Motor Classification Scores in EEG Data".
Thesis URL: http://hdl.handle.net/1773/50294

Modified and used with permission. 
"""

# Tested to work with WearableSensing's DSI-Streamer v.1.08.60.
# Other versions may not work. 

import tkinter as tk
from tkinter import scrolledtext, Frame, Menu, filedialog, messagebox, ttk
import socket
import threading
import time
import struct
import os
import sys
import logging
from pathlib import Path
import json
import requests

RELAX_PROMPT = "Relax"

class TestOption:
    def __init__(self, option_name='INIT', explanation='', relax_time=0, action_time=0, loop_times=0):
        self.name = option_name
        self.explanation = explanation

        self.action_time = action_time 
        self.relax_time = relax_time 
        self.loop_times = loop_times 
    
    def update_vals(self, explanation='', action_time=-1, relax_time=-1, loop_times=-1):
        self.explanation = explanation if explanation != '' else self.explanation

        self.action_time = float(action_time) if float(action_time) >= 0 else self.action_time
        self.relax_time = float(relax_time) if float(relax_time) >= 0 else self.relax_time
        self.loop_times = int(loop_times) if int(loop_times) >= 0 else self.loop_times
    
    def get_vals(self):
        return [
        ('Opt. Name', self.name),
        ('Explanation', self.explanation),
        ('Action Time (sec)', self.action_time),
        ('Relax Time (sec)', self.relax_time),
        ('Loop Count', self.loop_times)
    ]

class Test:
    def __init__(self, action_name: str, action_prompt: str):
        self.name = action_name
        self.action_prompt = action_prompt 

        self.options = {} # Dict. maps option_name (str) to TestOption.
    
    def num_of_options(self):
        return len(self.options)
    
    def empty(self):
        return (self.num_of_options() == 0)
        
    def add_opt(self, option: TestOption):
        if option.name in self.options:
            logging.warning(f"Can not add options with the same name '{option.name}' to a test.")
            return False
        
        self.options[option.name] = option
        return True
    
    def add_option(self, option_name='', explanation='', action_time=0, relax_time=0, loop_times=0):       
        newOpt = TestOption(option_name=option_name, explanation=explanation, action_time=action_time, relax_time=relax_time, loop_times=loop_times)
        return self.add_opt(newOpt)
    
    def delete_option(self, option):
        option_name = option if isinstance(option, str) else option.name if isinstance(option, TestOption) else None

        if option_name in self.options:
            del self.options[option_name]
            return True
        
        return False
    
    def update_option(self, option_name, explanation='', relax_time=-1, action_time=-1, loop_times=-1):
        if option_name in self.options:
            self.options[option_name].update_vals(explanation=explanation, relax_time=relax_time, action_time=action_time, loop_times=loop_times)
            return True
        
        return False
    
    def get_option(self, option_name: str) -> TestOption:
        return self.options.get(option_name, None)

class TestSettings:
    """
    For multiple timing options for a single test.
    E.g:
    Test: Eyeroll
            option 1: Block timing
            option 2: Single 4 secs timing
    """

    def __init__(self, dir: str, root):
        self.root = root

        self.all_tests = {} # Dicctionary mapping Test.name (str) to Test 
        self.load_from_json(dir=dir)

        self.top_frame = tk.Frame(self.root)
        self.top_frame.pack(side=tk.TOP, padx=10, pady=10)

        # Create a menu
        self.menubar = Menu(self.root)
        self.root.config(menu=self.menubar)

        # Create the settings_menu, and add the menu items:
        settings_menu = Menu(self.menubar, tearoff=0)

        settings_menu.add_command(
            label="Create/Delete Tests", command=self.open_test_settings_window
        )

        # Settings
        self.menubar.add_cascade(label="Settings", menu=settings_menu)

        # Instructions (TBD)
        self.menubar.add_command(label="Instructions", command=self.show_instructions)

        # Help (TDB)
        help_menu = Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
    
    def show_instructions(self):
        pass

    def load_json(self, filename, dir=None, max_download_attempts=1):
        # Change to directory that contains config file.
        if dir is not None:
            os.chdir(dir)

        # Load the json config file.
        json_filename = filename if filename.endswith('.json') else filename + '.json'
        
        for _ in range(max_download_attempts + 1): 
            try:
                with open(json_filename, 'r', encoding="utf-8") as file:
                    data = json.load(file)
                
                self.filename = json_filename
                return data

            except FileNotFoundError:
                self.download_config_file(json_filename)
        
        return None # On failure (after reaching allowed attempt count).
    
    def load_from_json(self, filename="experiment_config", dir=None, max_download_attempts=1):
        data = self.load_json(filename=filename, dir=dir, max_download_attempts=max_download_attempts)

        if data is None:
            return False

        # Update the script's datasctructures, using the data from the json config file. 
        for test_name, test_data in data.items():
            test = Test(test_name, test_data['Action Prompt']) # Create the new Test.

            for option in test_data["options"]: 
                # Add the current option to the current Test's 'options' map.
                test.add_option(option_name=option["Option type"], explanation=option["Explanation"], 
                                action_time=option["Action Time (secs)"], relax_time=option["Relax Time (secs)"], loop_times=option["Loop times"])
                        
            self.all_tests[test_name] = test # Add the new Test to all_tests.

        return True
    
    def download_config_file(self, filename):
        url = 'https://github.com/UW-Stroke-Rehab/Data-Collection/main/experiment_config.json'
        response = requests.get(url)

        if response.status_code == 200:
            with open(filename, 'wb') as file:
                file.write(response.content)

        else:
            raise Exception(f"Failed to download config file from {url}.")

    # Save updated all_tests value into JSON file
    def save_to_json(self):
        try:
            serializable_tests = {} # Custom objects need to be converted to serializable dictionaries.
            for test_name, test in self.all_tests.items():
                serializable_test = {
                    "Action Prompt": test.action_prompt,
                    "options": [
                        {
                            "Option type": option.name,
                            "Explanation": option.explanation,
                            "Relax Time (secs)": option.relax_time,
                            "Action Time (secs)": option.action_time,
                            "Loop times": option.loop_times
                        } for option in test.options.values()
                    ]
                }
                serializable_tests[test_name] = serializable_test

            # Save the serializable data to the JSON file
            with open(self.filename, "w") as f:
                json.dump(serializable_tests, f, indent=4) 

        except Exception as e:
            logging.error(f"\n{e}\n\nsave_to_json failed.\n\n")
            return False
        
        return True

    def delete_test(self, test):
        test_name = test if isinstance(test, str) else test.name if isinstance(test, Test) else None

        if test_name in self.all_tests:
            confirmed = messagebox.askyesno("Confirmation", f"Are you sure you want to delete the Test '{test_name}'?")

            if confirmed:
                del self.all_tests[test_name]

                self.save_to_json()
                self.show_all_tests()
                return True
        
        return False

    def create_new_option(
        self,
        test_name : str,
        option_title=None,
        explanation='TBD',
        relax_time=0,
        action_time=0,
        loop_times=0,
    ):
        if option_title is None:
            option_title = f"opt{(len(self.all_tests[test_name].options)) + 1}"

        # Udate data structure, then the json file.
        self.all_tests[test_name].add_option(option_name=option_title, explanation=explanation, action_time=action_time, relax_time=relax_time, loop_times=loop_times)
        self.save_to_json()

        # Update screen
        self.show_options(test_name=test_name)

    def delete_option(self, test_name, option_name, delete_empty_test=True):
        if (test_name not in self.all_tests):
            logging.warning(f"Cannot delete option from non-existing test '{test_name}'.")

        confirmed = messagebox.askyesno("Confirmation", f"Are you sure you want to delete the Option '{option_name}' from the Test '{test_name}'?")
        if not confirmed:
            return False

        test = self.all_tests[test_name]
        test.delete_option(option_name)

        if test.empty(): # No need to store a test that has no options. 
            self.delete_test(test=test_name)

        self.save_to_json()

        # Update display
        if delete_empty_test and test.empty():
            self.show_all_tests()
        else:
            self.show_options(test_name=test_name)
        
        return True

    # Creates new test. Optionally allows creating the first option.
    def create_new_test(
        self,
        test_name,
        action_prompt='',
        option_title=None,
        explanation="",
        action_time=0,
        relax_time=0,
        loop_times=0,
    ):        
        if test_name is None or test_name == '':
            return False

        if test_name in self.all_tests:
            logging.warning(f"Cannot create tests with the same name '{test_name}'.")
            return False
        
        if action_prompt == '':
            action_prompt = test_name
        
        new_test = Test(action_name=test_name, action_prompt=action_prompt)
        self.all_tests[test_name] = new_test

        if option_title is not None:
            self.all_tests[test_name].options[option_title] = TestOption(option_name=option_title, explanation=explanation, action_time=action_time, relax_time=relax_time, loop_times=loop_times)

        # Save updated values into JSON file
        return self.save_to_json()

    def open_test_settings_window(self, width=400, height=600):
        self.test_settings_window = tk.Toplevel(self.root)
        self.test_settings_window.geometry(f"{width}x{height}")
        self.test_settings_window.resizable(False, False)  # Make the window non-resizable

        canvas = tk.Canvas(self.test_settings_window)
        canvas.pack(side="left", fill="both", expand=True)

        content_frame = tk.Frame(canvas)
        canvas.create_window((0, 0), window=content_frame, anchor="nw")
        content_frame.bind(
            "<Configure>",
            lambda event: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        self.tests_content_frame = content_frame
        self.tests_content_frame.lift()

        # Display all options as buttons
        self.show_all_tests()

    def clear_frame(self, content_frame):
        # Destroy all child widgets and frames recursively
        for widget in content_frame.winfo_children():
            widget.destroy()

    def show_all_tests(self):
        self.clear_frame(self.tests_content_frame)

        # [TOP FRAME] Allow users to create new tests.
        top_frame = tk.Frame(self.tests_content_frame)
        top_frame.pack(side=tk.TOP)

        new_test_label = tk.Label(top_frame, text='Enter name for new test: ')
        new_test_label.pack(side=tk.TOP, anchor=tk.W)

        self.new_test_entry = tk.Entry(top_frame, width=17)
        self.new_test_entry.pack(side=tk.LEFT, padx=5)

        new_test_save_button = tk.Button(top_frame, text="Add", command=self.on_add_test, bg="lightgreen")
        new_test_save_button.pack(side=tk.LEFT)

        # [BOTTOM FRAME] Add buttons to allow navigation to each Test.
        bottom_frame = tk.Frame(self.tests_content_frame)
        bottom_frame.pack(side=tk.TOP)

        # Create a Listbox widget to hold the test names
        test_listbox = tk.Listbox(bottom_frame, height=10, width=50)
        test_listbox.pack(side=tk.LEFT, fill=tk.Y)

        # Create a Scrollbar widget and attach it to the Listbox
        scrollbar = tk.Scrollbar(bottom_frame, orient=tk.VERTICAL)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        scrollbar.config(command=test_listbox.yview)

        test_listbox.config(yscrollcommand=scrollbar.set)

        colors = ["#FFFFFF", "#c8e4f0"]
        for i, test_name in enumerate(self.all_tests):
            test_listbox.insert(tk.END, test_name)
            test_listbox.itemconfig(tk.END, bg=colors[i%2])
        
        test_listbox.bind("<<ListboxSelect>>", lambda event: self.on_test_selected(event))
    
    def on_add_test(self, event=None):
        test_name = self.new_test_entry.get() 

        if (self.create_new_test(test_name=test_name, option_title="Opt. 1")):
            test_listbox = self.tests_content_frame.winfo_children()[1].winfo_children()[0] 
            test_listbox.insert(tk.END, test_name)
            
            self.new_test_entry.delete(0, tk.END) # Clear entry

    def on_test_selected(self, event):
        selected_index = event.widget.curselection()

        if selected_index:
            selected_test_name = event.widget.get(selected_index[0])
            self.show_options(test_name=selected_test_name)

    def show_options(self, test_name : str):
        self.clear_frame(content_frame=self.tests_content_frame)
        self.show_test_header(test_name=test_name)
        self.show_test_options(test_name=test_name)
    
    def update_prompt(self, test_name: str, new_prompt: str):
        if new_prompt == '' or test_name not in self.all_tests:
            return False
        
        self.all_tests[test_name].action_prompt = new_prompt
        return True

    def show_test_header(self, test_name, header_x_padding=5, header_y_padding=1, bg="lightblue"):
        # Create the header frame
        header_frame = tk.Frame(self.tests_content_frame, width=200, bg=bg)
        header_frame.pack(fill=tk.X)

        # For sorting sections of the header frame
        top_frame = tk.Frame(header_frame, bg=bg)
        middle_frame = tk.Frame(header_frame, bg=bg)
        bottom_frame = tk.Frame(header_frame, bg=bg) 

        padding = 0.5
        top_frame.pack(side=tk.TOP, anchor="nw", padx=padding, pady=padding, expand=True)  
        middle_frame.pack(side=tk.TOP, anchor="s", padx=padding, pady=padding+7, expand=True)  
        bottom_frame.pack(side=tk.TOP, anchor="s", padx=padding, pady=padding, expand=True)  

        # Create a back button to return to all tests
        back_button = tk.Label(top_frame, text="Back", cursor="hand2", bg=bg)
        back_button.pack(side="left")
        back_button.bind("<Button-1>", lambda event: self.show_all_tests())

        # Add test title
        test_name_label = tk.Label(top_frame, text=f"'{test_name}' Test", font=("Arial", 12, "bold"), bg=bg)
        test_name_label.pack(side=tk.LEFT, padx=header_x_padding+60, pady=header_y_padding, expand=True)

        # Create a delete button for the entire test
        delete_test_button = tk.Label(
            top_frame,
            text="Delete entire Test",
            fg="red", bg=bg,
            cursor="hand2"
        )

        delete_test_button.pack(side=tk.RIGHT, anchor="e")
        delete_test_button.bind("<Button-1>",lambda event: self.delete_test(test=test_name))

        # Create the entry and update prompt button
        self.curr_action_prompt = tk.StringVar()
        prompt_entry = tk.Entry(middle_frame, textvariable=self.curr_action_prompt, width=15)
        prompt_entry.insert(tk.END, self.all_tests[test_name].action_prompt)
        prompt_entry.pack(side=tk.LEFT)

        prompt_button = tk.Button(middle_frame, text='Update Prompt', anchor="nw", command=lambda: self.update_prompt(prompt_entry.get(), test_name))
        prompt_button.pack(side=tk.LEFT, pady=header_y_padding, padx=header_x_padding)

        # Create button to create a new option for the current test
        new_option_button = tk.Label(
            bottom_frame,
            text="Create new option",
            fg="green", bg=bg,
            cursor="hand2",
        )

        new_option_button.pack(side=tk.LEFT, pady=header_y_padding)
        new_option_button.bind(
            "<Button-1>",
            lambda event: self.create_new_option(test_name=test_name),
        )

    def show_test_options(self, test_name : str, bg = "#c8e4f0"):
        width = self.test_settings_window.winfo_width() - 25
        height = self.test_settings_window.winfo_height()

        ##### CREATE scrollable frame for options #####
        details_frame = tk.Frame(self.tests_content_frame, width=width, height=height)
        details_frame.pack(fill=tk.BOTH, expand=True)

        details_canvas = tk.Canvas(details_frame, width=width, height=height)
        details_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar:
        scrollbar = tk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details_canvas.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        details_canvas.configure(yscrollcommand=scrollbar.set)

        details_canvas.bind("<Configure>", lambda event: self.bind_scrollable(event, details_canvas))
        details_canvas.bind_all("<MouseWheel>", lambda event: self.mousewheel_scroll(event, details_canvas))

        details_content_frame = tk.Frame(details_canvas)
        
        # Scrollable region
        details_canvas.create_window((0, 0), window=details_content_frame, anchor="nw")
        details_content_frame.bind("<Configure>", lambda event: self.bind_scrollable(event, details_canvas))

        ##### FILL options with details #####
        # Get the details for the selected test
        current_test = self.all_tests[test_name]

        option_frame_width = 150
        num_options = 0
        # Display each option for the test
        for _, option_name in enumerate(current_test.options):
            num_options += 1
            option = current_test.options[option_name]

            option_frame = tk.Frame( # Create a frame for each option
                details_content_frame,
                relief="solid",
                borderwidth=1,
                padx=10,
                pady=10,
                width=option_frame_width, bg=bg
            )
            option_frame.pack(pady=10, fill="both", expand=True, anchor="w", side="top")

            delete_option_icon = tk.Label( # Create a delete X-button for each option
                option_frame,
                text="X",
                font=("Arial", 12, "bold"),
                fg="red", bg=bg,
                cursor="hand2",
            )

            delete_option_icon.pack(anchor="ne", pady=1, padx=10)
            delete_option_icon.bind(
                "<Button-1>",
                lambda event: self.delete_option(test_name=current_test.name, option_name=option_name),
            )

            entries = []
            for label, value in option.get_vals(): # Add each value for the current option. 
                entry = self.add_box_detail(option_frame=option_frame, label=label, value=value, bg=bg)
                entries.append(entry)

            save_button = tk.Button(
                option_frame,
                text="Save",
                command=lambda entries=entries, test_name=test_name: self.save_updated_values(
                    test_name=test_name,
                    option_title=entries[0].get("1.0", "end-1c"),
                    explanation=entries[1].get("1.0", "end-1c"),
                    relax_time=entries[2].get("1.0", "end-1c"),
                    action_time=entries[3].get("1.0", "end-1c"),
                    loop_times=entries[4].get("1.0", "end-1c"),
                ),
            )
            save_button.pack(anchor="n", padx=option_frame_width)

        self.add_padding(content_frame=details_content_frame, bg="lightblue", text='[END]', font=("Arial", 10, "bold"))

        if (num_options > 1):
            self.add_padding(content_frame=details_content_frame, line_count=5)


    # Use entry to update variable values
    def save_updated_values(self, test_name, option_title, explanation, relax_time, action_time, loop_times):
        updated = self.all_tests[test_name].update_option(option_name=option_title, 
                                                          explanation=explanation, 
                                                          relax_time=relax_time, 
                                                          action_time=action_time, 
                                                          loop_times=loop_times)
        if updated:
            self.save_to_json()

        else:
            logging.warning('save_updated_values failed.')

    # Insert details for specific option
    def add_box_detail(self, option_frame, label: str, value, entry_width=40, bg=None):
        label = tk.Label(
            option_frame,
            text=label,
            wraplength=280,
            justify="left",
            bg=bg
        )
        label.pack(anchor="w")

        value_text = str(value)
        height = len(value_text) / (entry_width / 1.5)

        entry = tk.Text(
            option_frame, width=entry_width, height=height, wrap=tk.WORD
        )
        entry.insert(tk.END, value_text)
        entry.pack(anchor="w", expand=True)

        return entry

    # Helper method: Add extra lines to canvas
    def add_padding(self, content_frame, line_count=1, bg=None, text='', font=None):
        for i in range(line_count):
            space_label = tk.Label(content_frame, text=text, bg=bg, font=font)
            space_label.pack(side=tk.TOP, expand=True, fill=tk.X)

    # Helper: Update the scrollable region of the canvas
    def bind_scrollable(self, event, details_canvas):
        details_canvas.configure(scrollregion=details_canvas.bbox("all"))

    # Helper: Scroll the canvas vertically based on the mouse wheel delta
    def mousewheel_scroll(self, event, canvas):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def disable_settings(self):
        self.menubar.entryconfigure(1, state=tk.DISABLED)

    def enable_settings(self):
        self.menubar.entryconfigure(1, state=tk.DISABLED)

class DataCollectionGUI:
    def __init__(self, dir=None):
        self.WINDOW_HEADER_BG = '#eaebec'

        # File variables:
        self.file_name = '' # Temp
        self.file_extension = ".csv"

        self.file_dir = os.path.join(os.getcwd(), "DSI Data") if dir is None else dir
        if not os.path.exists(self.file_dir):
            os.makedirs(self.file_dir)

        self.full_path = os.path.join(self.file_dir, f"{self.file_name}{self.file_extension}") # Temp

        # Create the GUI
        self.root = tk.Tk()
        self.root.title("EEG Data Experiment and Collection")
        self.root.configure(bg=self.WINDOW_HEADER_BG)

        # Tell the window how to close correctly
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Top frame: Status label and Value Components
        self.top_frame = tk.Frame(self.root, bg=self.WINDOW_HEADER_BG)
        self.top_frame.pack(side=tk.TOP, padx=10, pady=10)

        self.status_label = tk.Label(self.top_frame, text="Status: ", bg=self.WINDOW_HEADER_BG)
        self.status_label.pack(side=tk.LEFT)

        self.status_value = tk.Label(self.top_frame, text="Waiting to begin...", bg=self.WINDOW_HEADER_BG)
        self.status_value.pack(side=tk.LEFT, padx=5)

        # Create the Timer
        self.timer_label = tk.Label(self.top_frame, text="Timer: ", bg=self.WINDOW_HEADER_BG)
        self.timer_label.pack(side=tk.LEFT)

        self.timer_value = tk.Label(self.top_frame, text="00:00:00", bg=self.WINDOW_HEADER_BG)
        self.timer_value.pack(side=tk.LEFT, padx=5)

        # Start button
        self.start_button = tk.Button(
            self.top_frame, text="Start", command=self.start
        )
        self.start_button.pack(side=tk.RIGHT, padx=10)
        self.start_button.config(state="disabled") # Can't start before choosing file.

        # Configure menu bar
        self.testSettings = TestSettings(dir=dir, root=self.root)

        ### (Middle Frame) Add dropdown boxes ### 
        self.middle_frame = tk.Frame(self.root, bg=self.WINDOW_HEADER_BG)
        self.middle_frame.pack(side=tk.TOP, padx=10, pady=10)       

        # Left dropdown: Select Test:
        t_label = tk.Label(self.middle_frame, text="Select Experiment Type:", bg=self.WINDOW_HEADER_BG)
        t_label.pack(side=tk.LEFT)

        self.t_variable = tk.StringVar()
        self.test_dropdown = ttk.Combobox(
            self.middle_frame, textvariable=self.t_variable, state="readonly"
        )

        t_list = list(self.test_dropdown["values"])
        for test_name in self.testSettings.all_tests:
            t_list.append(str(test_name)) # Tuples are immutable, so utilize a list.

        self.test_dropdown["values"] = tuple(t_list)
        self.test_dropdown.pack(side=tk.LEFT, padx=5)

        # Right dropdown: Select Option:
        opt_label = tk.Label(self.middle_frame, text="Select Timing:", bg=self.WINDOW_HEADER_BG)
        opt_label.pack(side=tk.LEFT)

        self.opt_variable = tk.StringVar()
        self.options_dropdown  = ttk.Combobox(
            self.middle_frame, textvariable=self.opt_variable, state="readonly"
        )
        self.options_dropdown.pack(side=tk.LEFT, padx=5)

        # Options update based on selected test.
        self.t_variable.trace_add("write", self.update_options_dropdown)

        ## Bottom Frame ###
        bottom_frame = tk.Frame(self.root, bg=self.WINDOW_HEADER_BG)
        bottom_frame.pack(side=tk.TOP, padx=10, pady=10)

        # File selection:
        file_label = tk.Label(bottom_frame, text="Enter filename:", bg=self.WINDOW_HEADER_BG)
        file_label.pack(side=tk.LEFT)

        self.filename_entry = tk.Entry(bottom_frame, width=45)
        self.filename_entry.pack(side=tk.LEFT, padx=5)
        self.filename_entry.bind("<KeyRelease>", self.update_file_entry)

        or_label = tk.Label(bottom_frame, text=" OR:", bg=self.WINDOW_HEADER_BG)
        or_label.pack(side=tk.LEFT)

        self.file_button = tk.Button(bottom_frame, text="Open File Explorer", command=lambda: self.save_file_to(dir=dir, filetype='csv'))
        self.file_button.pack(side=tk.RIGHT, padx=5)

        ### Main Frame ###
        self.main_frame = tk.Frame(self.root, bg=self.WINDOW_HEADER_BG)
        self.main_frame.pack(side=tk.TOP, padx=10, pady=10)

        # Textbox (with Scrollbar) for diagnostics and output
        self.text_box = scrolledtext.ScrolledText(self.main_frame, width=50, height=20)
        self.text_box.pack(side=tk.LEFT)

        # Always see most current text in textbox (scrolls up when needed)
        self.text_box.bind('<Key>', lambda event: self.text_box.yview(tk.END))

        self.text_box.tag_configure("red", foreground="red")
        self.text_box.tag_configure("black", foreground="black")
        self.text_box.tag_configure("orange", foreground="orange red")
        self.text_box.tag_configure("green", foreground="green")
        self.text_box.tag_configure("blue", foreground="blue")

        self.scrollbar = tk.Scrollbar(self.main_frame)
        self.scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        self.text_box.config(yscrollcommand=self.scrollbar.set)
        self.scrollbar.config(command=self.text_box.yview)

        # Print first messages to text box
        self.insert_text(text_box=self.text_box, txt='Socket not connected.\n', tag='blue')
        self.insert_text(text_box=self.text_box, txt='Enter filename and press Start to begin.\n', tag='blue')

        # Connection variables: 
        self.socket = None
        self.TCP_IP = "localhost"
        self.TCP_PORT = 8844
        self.timer_running = False
        self.socket_running = False
        self.time_point_set = False
        self.start_time_stamp = None
        self.last_time_stamp = None
        self.backlog_time_stamp = None
        self.collection_duration = None
        self.seconds = 0
        self.minutes = 0
        self.prompt_dictionary = None
        self.DSI_EVENT_CODES = {
            1: "Greeting/Version",
            2: "Data Start",
            3: "Data Stop",
            4: "Reserved",
            5: "Reserved",
            6: "Reserved",
            7: "Reserved",
            8: "Reserved",
            9: "Sensor Map",
            10: "Data Rate",
        }
        
    def scroll_textbox_to_end(self):
        self.text_box.see(tk.END)

    def on_closing(self):
        """
        Code to run when window is closing.
        """
        print("Closing window...")
        
        self.socket_running = False
        self.timer_running = False

        try:
            self.socket.close()
        except:
            pass

        try:
            self.file.close()
        except:
            pass

        self.root.destroy()  # Close the window
    
    def update_options_dropdown(self, *_args):
        selected_test_name = self.t_variable.get()

        if selected_test_name in self.testSettings.all_tests:
            options = self.testSettings.all_tests[selected_test_name].options.keys()

            self.options_dropdown["values"] = tuple(options)

            # By default, select the first option (a Test should have 1+ options).
            self.opt_variable.set(next(iter(options)) if options else "")

            self.toggle_start_button()
    
    def save_file_to(self, filetype=None, dir=None):
        if dir is not None:
            self.file_dir = dir
        
        if filetype is not None:
            self.file_extension = filetype
            filetypes = [("All files", "*.*")]

        else:
            filetypes = [(filetype.upper(), f"*.{filetype}")]

        full_path = filedialog.asksaveasfilename(initialdir=dir, filetypes=filetypes)
        self.filename_entry.delete(0, tk.END) # Clear old entry
        self.update_file_entry(new_full_path=full_path)
    
    def update_filename(self, new_filename=None, new_full_path=None):
        """
        If new_filename is provided, replaces current name.
        Otherwise uses current full_path.

        Separates the following from the full_path:
          file_directory, file_name, and file_extension
        
          Appends the test and option selection to the filename.
        """
        tail_indicator = "-" # Should not be underscore ('_').

        if new_full_path:
            self.full_path = new_full_path

            self.file_dir = os.path.dirname(new_full_path)
            file_name_ext = os.path.basename(new_full_path)
            self.file_name, self.file_extension = os.path.splitext(file_name_ext)

        else: # Providing full path overwrited providing name. 
            if new_filename and new_filename != '':
                self.file_name = new_filename

            else:
                self.file_name = self.filename_entry.get()            
        
        # Delete old tails, if any.
        #old_tail_start = file_name.find(tail_indicator)
        #file_name = file_name[:old_tail_start] if old_tail_start != -1 else file_name
        
        # Filename may not have tail indicator other than right before the tail.
        self.file_name = self.file_name.replace(tail_indicator, "_")
        self.file_name = self.file_name.replace(" ", "_") # Remove spaces as well.

        curr_test = self.t_variable.get()
        curr_opt = self.opt_variable.get()

        # For appending selected test and option to the name.
        self.tail = f"{tail_indicator}{curr_test}_{curr_opt}"

        # Append file count (to deal with identically named files).
        counter = 1
        while os.path.exists(os.path.join(self.file_dir, f"{self.file_name}{self.tail}_{counter}")):
            counter += 1
        
        self.tail = f"{self.tail}_{counter}"
        self.tail = self.tail.replace(" ", "_") 

        # Update full_path to reflect changes.
        self.full_path = os.path.join(self.file_dir, f"{self.file_name}{self.tail}{self.file_extension}")

    
    def toggle_start_button(self):
        if (self.full_path != "" and self.filename_entry.get() != "" and
            self.test_dropdown.get() != "" and self.options_dropdown.get() != ""):

            self.start_button.configure(state="normal")

        else:
            self.start_button.configure(state="disabled")
        

        button_text = self.start_button.cget("text")
        if button_text.lower() == "start":
            self.start_button.config(text="Start", foreground="green")

        elif button_text.lower() == "stop":
            self.start_button.config(text="Stop", foreground="red")
    
    def update_file_entry(self, event=None, new_filename=None, new_full_path=None):            
        self.update_filename(new_filename=new_filename, new_full_path=new_full_path)

        # Clear previous entry and update
        self.filename_entry.delete(0, tk.END)  
        self.filename_entry.insert(0, self.file_name) 

        # Check if start button meets requirements, and enable if so.
        self.toggle_start_button()
    
    def restart(self):
        self.start_button.config(text="Start", foreground="green")
        self.set_button_state(state="normal")
        self.testSettings.enable_settings()

        self.status_value.config(text="Waiting to begin...")
    
    def determine_collection_duration(self):
        """
        Also sets self.prompt_dictionary.
        @TODO: Replace using this for printing time stamps.
        """
        
        test = self.testSettings.all_tests[str(self.t_variable.get())]
        option = test.options[str(self.opt_variable.get())] 

        # Set prompt_dictionary:
        self.prompt_dictionary = {}
        last_timestamp = 0

        self.prompt_dictionary[0] =  RELAX_PROMPT

        for i in range(option.loop_times):
            time_till_act = option.relax_time + last_timestamp
            time_till_rest = option.action_time + time_till_act

            self.prompt_dictionary[time_till_act] = test.action_prompt
            self.prompt_dictionary[time_till_rest] = RELAX_PROMPT

            last_timestamp = time_till_rest
        
        self.prompt_dictionary[last_timestamp + option.relax_time] = RELAX_PROMPT

        # Return collection duration
        collection_duration = list(self.prompt_dictionary.keys())[-1]
        return collection_duration
    
    def insert_text(self, text_box, txt, tag=''):
        if not txt.endswith('\n'):
            txt += '\n'

        text_box.insert(tk.END, txt, tag)
        text_box.see(tk.END)

    def start(self):
        self.set_button_state("disabled")

        if not self.socket_running:
            if self.open_socket() == False:
                self.insert_text(self.text_box, txt='Connection Refused!\n ABORTING...\n', tag='red')

                self.restart()
                return 
        
            # Clear the Textbox, then add confirmation message. 
            self.text_box.delete("1.0", tk.END)
            self.insert_text(self.text_box, txt='Socket connected.\n\n', tag='green')
 
            # Print file directory:
            self.insert_text(self.text_box, txt='File Name: ', tag='black')
            self.insert_text(self.text_box, txt=f"{self.file_name}{self.tail}_{self.file_extension}\n", tag='blue')
            self.insert_text(self.text_box, txt=f"File Directory: \n", tag='black')
            self.insert_text(self.text_box, txt=f"{self.file_dir}\n\n", tag='blue')

            self.file = open(self.full_path, "w")

            # Timing: @TODO: Replace using a list. 
            self.collection_duration = self.determine_collection_duration()

            # Start socket loop:
            self.socket_running = True
            threading.Thread(target=self.socket_loop).start()

            # Upgrade status labels: 
            self.status_label.config(text="Active")
            self.start_button.config(text="Stop", foreground="red")
        
        else: # if socket_running = True
            self.socket_running = False
            self.timer_running = False

            self.insert_text(self.text_box, txt='Collection ending...\n')
            self.restart()

    def set_button_state(self, state: str):
        """
        State should be "normal" or "disabled".
        """

        if state == "disabled":
            self.testSettings.disable_settings()
        else:
            self.testSettings.enable_settings()

        self.test_dropdown.config(state=state)
        self.options_dropdown.config(state=state)

        self.filename_entry.config(state=state)
        self.file_button.config(state=state)
    
    def open_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024)

        try:
            self.socket.connect((self.TCP_IP, self.TCP_PORT))

        except:
            return False
        
        return True
    
    def socket_loop(self):
        while self.socket_running: 
            if not self.receive_and_handle_data(): # Get the Packet Header
                break

        backlog_packet_counter = 0

        if (self.last_time_stamp - self.start_time_stamp) < float(self.collection_duration):
            self.insert_text(self.text_box, txt='Capturing Backlog Data from DSI!\n')
            self.insert_text(self.text_box, txt='Do not close the window or the DSI-Streamer, \nor data will be lost!\n', tag='orange')

            self.set_button_state("disabled")

        self.backlog_time_stamp = self.last_time_stamp

        while self.last_time_stamp - self.start_time_stamp < float(self.collection_duration):
            if not self.receive_and_handle_data():
                break

            backlog_packet_counter = backlog_packet_counter + 1

        self.socket.close()
        self.file.close()

        self.insert_text(self.text_box, txt="Received {:.2f} seconds of Backlog from DSI!\n".format(self.last_time_stamp - self.backlog_time_stamp))
        self.insert_text(self.text_box, txt="Collection began at {:.2f} seconds\n".format(self.start_time_stamp))
        self.insert_text(self.text_box, txt="Backlog began at {:.2f} seconds\n".format(self.backlog_time_stamp))
        self.insert_text(self.text_box, txt="Backlog ended at {:.2f} seconds\n".format(self.last_time_stamp))        

        self.start_time_stamp = None
        self.last_time_stamp = None
        self.insert_text(self.text_box, txt='Data Collection Loop Ending!\n', tag='green')

        self.set_button_state("normal")
        self.start_button.config(state="normal")
        self.start_button.config(text="Start")

    def time_loop(self):
        self.text_box.tag_configure('bg_lightblue', background='#c8e4f0')

        while self.timer_running:
            self.seconds += 1
            if self.seconds == 60:
                self.seconds = 0
                self.minutes += 1

            time_string = "{:02d}:{:02d}".format(self.minutes, self.seconds)
            self.timer_value.config(text=time_string)

            if (self.seconds in self.prompt_dictionary and self.prompt_dictionary[self.seconds] is not None):
                prompt = self.prompt_dictionary[self.seconds]
                text = "{:02d}: {}".format(self.seconds, prompt)

                if prompt != RELAX_PROMPT:
                    bg = 'bg_lightblue'
                else:
                    bg = ''

                self.insert_text(self.text_box, txt=text, tag=bg)

            time.sleep(1) # second

            if self.seconds == self.collection_duration:
                self.insert_text(text_box=self.text_box, txt='\nTimer Expired!\n')
                self.start()

        self.seconds = 0
        self.minutes = 0

    def recvall(self, count):
        # Keep receiving data until we have received the requested number of bytes
        received = 0
        data = b""

        while received < count: # Receive up to count bytes of data
            try:
                chunk = self.socket.recv(count - received)
            except:
                return None
            
            if not chunk: # The other end closed the connection
                return None
            
            received += len(chunk)
            data += chunk

        return data

    def receive_and_handle_data(self):
        data = self.recvall(12)

        if not data:
            self.insert_text(text_box=self.text_box, txt='No Data Remaining in Socket!\n')
            return False
        
        # Get the Packet Type and the Packet Message Length.
        packet_type = int.from_bytes(data[5:6], byteorder="big", signed=False)
        data_length = int.from_bytes(data[6:8], byteorder="big", signed=False)

        # Get the Packet Body
        new_data = self.recvall(data_length)
        if not new_data:
            self.insert_text(text_box=self.text_box, txt='No Data Remaining in Socket!\n')
            return False
        data = data + new_data

        if packet_type == 5:
            # There is useful information in these event packets that is worth saving as comments at the head of the CSV file.
            event_code = int.from_bytes(data[12:16], byteorder="big", signed=False)
            if (event_code in self.DSI_EVENT_CODES and self.DSI_EVENT_CODES[event_code] is not None):
                event_string = self.DSI_EVENT_CODES[event_code]

            else:
                event_string = "UNKNOWN"
            
            self.insert_text(text_box=self.text_box, txt="Event Packet! Type: {}\n".format(event_string))

            if event_code == 2:
                self.insert_text(text_box=self.text_box, txt='\nBeginning Collection...\n\n', tag='green')
                self.timer_running = True
                threading.Thread(target=self.time_loop).start()

        elif packet_type == 1:
            # logging.info("INFO: Data Packet!")
            time_stamp = struct.unpack(">f", data[12:16])
            if self.start_time_stamp == None:
                self.start_time_stamp = time_stamp[0]
            self.last_time_stamp = time_stamp[0]

            eeg_data = struct.unpack(">25f", data[23 : len(data)])

            line = str(time_stamp[0]) + "," + ",".join([str(num) for num in eeg_data])

            self.file.write(line)
            self.file.write("\n")

        else:
            self.insert_text(textbox=self.text_box, txt='Reserved Packet!\n')

        return True
        
gui = DataCollectionGUI(dir=None)
gui.root.mainloop()
