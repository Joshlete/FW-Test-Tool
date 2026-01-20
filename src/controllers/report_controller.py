import os
import json

class ReportBuilder:
    def __init__(self, directory, step_number, strategy=None):
        self.directory = directory
        self.step_number = str(step_number)
        self.step_prefix = f"{self.step_number}. "
        self.strategy = strategy
    
    def scan_files(self):
        """
        Scans for all files belonging to the current step and categorizes them.
        Returns a dict of available categories and their file paths.
        """
        found_items = {
            "alerts": [],
            "suppliesPrivate": [],
            "suppliesPublic": [],
            "supplyAssessment": [],
            "DSR Packet": [],
            "Telemetry": [],
            "Other": []
        }
        
        if not os.path.exists(self.directory):
            return found_items

        try:
            for f in os.listdir(self.directory):
                # Must start with "Step. " e.g. "1. "
                if not f.startswith(self.step_prefix):
                    continue
                    
                full_path = os.path.join(self.directory, f)
                if not os.path.isfile(full_path):
                    continue
                    
                lower_name = f.lower()
                
                # Categorize based on filename keywords
                if "alert" in lower_name and "cdm" in lower_name:
                    found_items["alerts"].append(full_path)
                elif "suppliesprivate" in lower_name:
                    found_items["suppliesPrivate"].append(full_path)
                elif "suppliespublic" in lower_name:
                    found_items["suppliesPublic"].append(full_path)
                elif "supplyassessment" in lower_name:
                    found_items["supplyAssessment"].append(full_path)
                elif "dsr" in lower_name:
                    found_items["DSR Packet"].append(full_path)
                elif "telemetry" in lower_name:
                    found_items["Telemetry"].append(full_path)
                else:
                    found_items["Other"].append(full_path)
        except OSError:
            pass
                
        return found_items

    def get_telemetry_color_label_from_file(self, file_path):
        """
        Determines the display label (e.g., 'Black', 'Cyan', 'Tri-Color') for a telemetry file.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                return "Unknown"
            data = json.loads(content)
        except Exception:
            return "Unknown"

        supply_code = None
        try:
            if "eventDetail" in data and "identityInfo" in data["eventDetail"]:
                supply_code = data["eventDetail"]["identityInfo"].get("supplyColorCode")
        except Exception:
            supply_code = None

        if not supply_code:
            return "Unknown"

        code = str(supply_code).strip().upper()

        # Strategy-specific labels
        if self.strategy and self.strategy.get_name() == "Dune IPH":
            return "Black" if code == "K" else "Tri-Color"

        # Default (IIC-like): C/M/Y/K -> names
        return {
            "C": "Cyan",
            "M": "Magenta",
            "Y": "Yellow",
            "K": "Black",
        }.get(code, "Unknown")

    def get_available_alerts(self):
        """
        Scans alert files and returns a list of alert details.
        Returns: [ {id, category, visibility, file_path}, ... ]
        """
        found = self.scan_files()
        alert_files = found.get("alerts", [])
        alerts_list = []
        
        for f_path in alert_files:
            try:
                with open(f_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    data = json.loads(content)
                    if "alerts" in data and isinstance(data["alerts"], list):
                        for alert in data["alerts"]:
                            alerts_list.append({
                                "id": alert.get("id"),
                                "category": alert.get("category", "Unknown"),
                                "visibility": alert.get("visibility", ""),
                                "file_path": f_path
                            })
            except:
                pass
        return alerts_list

    def generate_report(self, selected_categories, colors=None, selected_alerts=None):
        """
        Builds the text report based on selected categories.
        selected_categories: dict of {category_name: [file_paths]}
        colors: list of strings (e.g. ["Cyan", "Magenta"]) to filter Telemetry/Supplies
        selected_alerts: Now used as a boolean/flag. If "alerts" category is present in selected_categories, 
                         we auto-include alerts matching the selected 'colors'.
        """
        if colors is None:
            colors = []
        
        # New Logic: Determine which Alert IDs we care about based on selected colors
        target_alert_ids = []
        include_alerts = "alerts" in selected_categories
        
        if include_alerts and colors:
            for c in colors:
                if self.strategy:
                    # Strategy-driven ID lookup
                    aid = self.strategy.get_alert_id(c)
                    if aid:
                        target_alert_ids.append(aid)
                # Fallback to hardcoded if no strategy (Legacy/Backup)
                elif c == "Cyan": target_alert_ids.append(103)
                elif c == "Magenta": target_alert_ids.append(104)
                elif c == "Yellow": target_alert_ids.append(101)
                elif c == "Black": target_alert_ids.append(102)

        output = []
        
        # 1. Header (Dynamic in main app, but we keep this as fallback)
        output.append(f"UI, EWS, CDM, and Telemetry were correct and to spec.")
        output.append("")
        
        empty_lines_when_no_content = 3
        sections = ["suppliesPrivate", "suppliesPublic", "supplyAssessment", "DSR Packet"]
        
        # We will process alerts differently: Only if 'alerts' is selected, we look for them.
        # But where do we put them? Usually they are separate blocks.
        # Let's stick to the section order, but for "alerts", we use the target_ids.
        
        # If alerts is selected, add it to sections list to be processed
        if include_alerts:
             sections.insert(0, "alerts") # Put alerts first or last? Usually top.

        for section in sections:
            # Only include sections that were selected (even if there are no files yet)
            if section not in selected_categories:
                continue

            files = selected_categories.get(section, [])
            # For alerts, we might not have 'files' passed if the UI logic removed it from the map because no file was explicitly checked.
            # But scan_files finds them. The UI passes what is selected.
            # If "Alerts" toggle is ON, the UI should pass the alert files in selected_categories["alerts"].
            
            # Determine processor based on section
            if section == "alerts":
                processor = lambda c: self._process_alerts_json(c, target_alert_ids)
            elif "supplies" in section:
                processor = lambda c: self._process_supplies_json(c, colors)
            elif section in ["supplyAssessment", "DSR Packet"]:
                processor = lambda c: self._process_color_coded_json(c, colors)
            else:
                processor = self._process_generic_json

            section_lines = self._build_section(
                section,
                files,
                processor,
                force_header=True,
                empty_line_count=empty_lines_when_no_content,
            )
            output.extend(section_lines)

        # 3. Process Tap (Manual Input)
        # UI stores this as selected_categories["Tap"] = ["43-Tap"] or ["63-Tap"] (display label).
        tap_label = None
        tap_value = selected_categories.get("Tap")
        if isinstance(tap_value, list) and tap_value:
            tap_label = tap_value[0]
        elif "Tap" in selected_categories:
            # Fallback: infer from strategy when UI didn't provide a label
            if self.strategy and self.strategy.get_name() == "Dune IPH":
                tap_label = "43-Tap"
            else:
                tap_label = "63-Tap"

        if tap_label:
            output.append(self._format_section_header(tap_label))
            output.extend([""] * empty_lines_when_no_content)  # Blank space for manual input
            # Note: No content generation needed

        # 4. Process Telemetry
        # - If Telemetry was selected but no files are selected yet, print a single empty Telemetry header.
        # - If telemetry files are selected, print separate sections per color label.
        if "Telemetry" in selected_categories:
            telemetry_files = selected_categories.get("Telemetry", [])
            if not telemetry_files:
                output.append(self._format_section_header("Telemetry"))
                output.extend([""] * empty_lines_when_no_content)
            else:
                grouped = {}
                for p in telemetry_files:
                    label = self.get_telemetry_color_label_from_file(p)
                    grouped.setdefault(label, []).append(p)

                # Preserve a reasonable order (strategy cartridge order first, then Unknown)
                ordered_labels = []
                if self.strategy:
                    ordered_labels.extend(self.strategy.get_cartridges())
                for lbl in grouped.keys():
                    if lbl not in ordered_labels:
                        ordered_labels.append(lbl)

                for lbl in ordered_labels:
                    files = grouped.get(lbl)
                    if not files:
                        continue
                    processed = self._process_telemetry(files)
                    output.append(self._format_section_header(f"Telemetry {lbl}"))
                    if processed:
                        output.append("")
                        output.extend(processed)
                        output.append("")
                    else:
                        output.extend([""] * empty_lines_when_no_content)

        # 5. Process "Other"
        other_files = selected_categories.get("Other", [])
        if other_files:
            output.append(self._format_section_header("Other"))
            output.append("")  # Blank line after header
            for f in other_files:
                output.append(f"Included: {os.path.basename(f)}")
            output.append("")  # Blank line after content

        # 6. Add single footer at the end if we have content
        if len(output) > 2:  # More than just the default header
            output.append("==================================================")

        return "\n".join(output)

    def _build_section(self, section_name, file_paths, processor_func, force_header=False, empty_line_count=3):
        """
        Builds a section as a list of lines.
        If force_header is True, the header is returned even if there is no content, followed by empty_line_count blanks.
        """
        header = self._format_section_header(section_name)
        lines = []

        # No files: either empty section or skip
        if not file_paths:
            if force_header:
                lines.append(header)
                lines.extend([""] * empty_line_count)
            return lines

        content_lines = []
        valid_data_found = False

        for file_path in file_paths:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    file_content = f.read()

                processed_text = processor_func(file_content)

                # If processor returned empty string (e.g. no matching colors), skip it
                if processed_text.strip() == "" or processed_text.strip() == "{}":
                    continue

                content_lines.extend(processed_text.splitlines())
                content_lines.append("")  # blank line between file blocks
                valid_data_found = True
            except Exception as e:
                content_lines.append(f"Error reading {os.path.basename(file_path)}: {str(e)}")
                content_lines.append("")
                valid_data_found = True

        if not valid_data_found:
            if force_header:
                lines.append(header)
                lines.extend([""] * empty_line_count)
            return lines

        # Trim trailing blanks
        while content_lines and content_lines[-1] == "":
            content_lines.pop()

        lines.append(header)
        lines.append("")  # blank line after header
        lines.extend(content_lines)
        lines.append("")  # blank line after section
        return lines

    def _format_section_header(self, name):
        total_len = 50
        name_len = len(name)
        side_len = (total_len - name_len - 2) // 2
        return "=" * side_len + f" {name} " + "=" * side_len + ("=" if (total_len - name_len - 2) % 2 else "")

    def _process_generic_json(self, content):
        """Standard pretty print for JSON"""
        try:
            data = json.loads(content)
            if not data: return content.strip()
            result = json.dumps(data, indent=4)
            # Add tab prefix to each line for consistency
            tab_prefixed = '\t' + result.replace('\n', '\n\t')
            return tab_prefixed
        except:
            return content.strip()

    def _process_color_coded_json(self, content, colors):
        """
        Generic processor for JSON files that need color filtering (Supply Assessment, DSR).
        Checks for 'colorCode' or 'supplyColorCode' matching selected colors.
        """
        try:
            data = json.loads(content)
            if not data: return content.strip()
            
            if not colors:
                return "" # consistent with other color-filtered sections
            
            # Helper to check if an object matches selected colors
            def match_color(obj):
                # Check directly in obj
                code = obj.get("colorCode") or obj.get("supplyColorCode")
                
                # Check nested in publicInformation (like suppliesPrivate)
                if not code and "publicInformation" in obj:
                     code = obj["publicInformation"].get("colorCode") or obj["publicInformation"].get("supplyColorCode")

                # If still not found, check if 'colors' array exists
                if not code:
                     obj_colors = obj.get("colors")
                     if not obj_colors and "publicInformation" in obj:
                         obj_colors = obj["publicInformation"].get("colors")
                     
                     if obj_colors and isinstance(obj_colors, list) and len(obj_colors) == 1:
                         code = obj_colors[0]

                if not code: return False

                # Strategy-driven matching (handles IPH Tri-Color ⇔ CMY, etc.)
                if self.strategy:
                    try:
                        return self.strategy.matches_color_code(code, colors)
                    except Exception:
                        # Fallback to legacy behavior below if strategy method misbehaves
                        pass

                # Legacy fallback matching (IIC-style)
                code = str(code).lower()
                for c in colors:
                    c_lower = c.lower()
                    if c_lower == "cyan" and ("c" == code or "cyan" in code): return True
                    if c_lower == "magenta" and ("m" == code or "magenta" in code): return True
                    if c_lower == "yellow" and ("y" == code or "yellow" in code): return True
                    if c_lower == "black" and ("k" == code or "black" in code): return True
                return False

            # Filter Logic (Handle Lists vs Dicts)
            if isinstance(data, list):
                filtered = [item for item in data if match_color(item)]
                if not filtered: return ""
                # Unwrap list items just like supplies
                output_parts = [json.dumps(item, indent=4) for item in filtered]
                result = "\n\n".join(output_parts)
                return '\t' + result.replace('\n', '\n\t')
            
            elif isinstance(data, dict):
                # 1. Check for 'supplyStates' wrapper (Supply Assessment)
                target_dict = None
                if "supplyStates" in data and isinstance(data["supplyStates"], dict):
                    target_dict = data["supplyStates"]
                # 2. Check for 'supplyStatus' -> 'supplyStates' (DSR Packet)
                elif "supplyStatus" in data and isinstance(data["supplyStatus"], dict):
                    if "supplyStates" in data["supplyStatus"] and isinstance(data["supplyStatus"]["supplyStates"], dict):
                        target_dict = data["supplyStatus"]["supplyStates"]
                
                # If we found a target container, use it. Otherwise use root data.
                source_to_iterate = target_dict if target_dict else data
                
                # If it's a dict, check if it's a wrapper like suppliesList
                if "suppliesList" in source_to_iterate and isinstance(source_to_iterate["suppliesList"], list):
                     filtered = [item for item in source_to_iterate["suppliesList"] if match_color(item)]
                     if not filtered: return ""
                     output_parts = [json.dumps(item, indent=4) for item in filtered]
                     result = ",\n\n".join(output_parts)
                     return '\t' + result.replace('\n', '\n\t')

                # Or just keyed objects (inkCartridge0, K, C, etc)
                output_parts = []
                sorted_keys = sorted(source_to_iterate.keys())
                
                for key in sorted_keys:
                    val = source_to_iterate[key]
                    if isinstance(val, dict):
                         if match_color(val):
                             # Unwrap: Key + Value
                             wrapper = {key: val}
                             dumped = json.dumps(wrapper, indent=4)
                             # Strip braces
                             lines = dumped.split('\n')
                             if len(lines) >= 2:
                                inner = '\n'.join(lines[1:-1])
                                output_parts.append(inner.strip(","))

                if output_parts:
                    # Join with comma and newlines to mimic original object structure but unwrapped
                    result = ",\n\n".join(output_parts)
                    return '\t' + result.replace('\n', '\n\t')
                
                return ""
                
        except:
             return content.strip()

    def _process_alerts_json(self, content, target_ids=None):
        """
        Process alerts JSON. 
        If target_ids is provided (list of ints), keep only alerts with those IDs.
        If target_ids is Empty list [], it means NO alerts match the criteria -> return empty.
        """
        try:
            data = json.loads(content)
            if not data or "alerts" not in data: 
                return content.strip()
            
            # Filter Logic
            filtered_alerts = []
            if target_ids is None:
                # If None passed, implies "All" or "Raw" - but our new logic always passes a list
                filtered_alerts = data["alerts"]
            else:
                # Only keep alerts whose ID is in the target list
                # Logic: Check if any item in the data array has a matching iValue
                for alert in data["alerts"]:
                    # Check nested data structure for iValue
                    matched = False
                    if "data" in alert and isinstance(alert["data"], list):
                        for item in alert["data"]:
                            if "value" in item and "iValue" in item["value"]:
                                if item["value"]["iValue"] in target_ids:
                                    matched = True
                                    break
                    
                    if matched:
                        filtered_alerts.append(alert)
            
            if not filtered_alerts:
                return "" # No matching alerts found
                
            # Unwrap: Format each alert object individually
            output_parts = []
            for alert in filtered_alerts:
                alert_json = json.dumps(alert, indent=4)
                output_parts.append(alert_json)
            
            result = "\n\n".join(output_parts)
            
            # Add tab prefix to each line for consistency
            tab_prefixed = '\t' + result.replace('\n', '\n\t')
            return tab_prefixed
        except:
            return content.strip()

    def _process_supplies_json(self, content, colors):
        """Filter supplies by single color match and unwrap content."""
        try:
            data = json.loads(content)
            if not data: return content.strip()
            
            # If no colors selected, return empty string (effectively skipping)
            if not colors:
                return ""
            
            # Filter first to get only valid objects
            filtered_data = self._filter_supplies_data(data, colors)
            
            # Now extract/unwrap based on structure
            output_parts = []
            
            if isinstance(filtered_data, dict):
                # Public: {"suppliesList": [...]}
                if "suppliesList" in filtered_data and isinstance(filtered_data["suppliesList"], list):
                     for item in filtered_data["suppliesList"]:
                         output_parts.append(json.dumps(item, indent=4))
                         
                # Private: {"inkCartridge1": {...}, ...}
                # (Note: _filter_supplies_data already removed non-matching keys)
                else:
                    # Iterate remaining keys
                    # Sort keys to ensure consistent order (e.g. inkCartridge0 then 1)
                    sorted_keys = sorted([k for k in filtered_data.keys() if k != "version"])
                    for key in sorted_keys:
                        val = filtered_data[key]
                        # Create "key": { ... } string manually
                        
                        # Approach: Dump {"key": val} and strip first/last line (the braces)
                        wrapper = {key: val}
                        dumped = json.dumps(wrapper, indent=4)
                        # Remove first line ({) and last line (})
                        lines = dumped.split('\n')
                        if len(lines) >= 2:
                            inner_content = '\n'.join(lines[1:-1])
                            output_parts.append(inner_content.strip(",")) # Strip potential trailing comma if it existed (it won't in single obj)

            if not output_parts:
                return ""

            # Join parts with comma if needed, or just newlines?
            is_public = "suppliesList" in data or ("suppliesList" in filtered_data)
            separator = ",\n\n" if not is_public else ",\n\n" 
            
            result = separator.join(output_parts)
            
            # Add tab prefix to each line for consistency with saved files
            tab_prefixed = '\t' + result.replace('\n', '\n\t')
            return tab_prefixed

        except:
            return content.strip()
            
    def _filter_supplies_data(self, data, colors):
        """
        Filters supplies data. 
        Uses Strategy if available, else falls back to legacy logic.
        """
        def is_valid_supply(supply_obj):
            if self.strategy:
                return self.strategy.is_valid_supply(supply_obj, colors)

            # --- Legacy Logic (IIC Only) ---
            # 1. Check colors list length
            obj_colors = []
            if "publicInformation" in supply_obj and "colors" in supply_obj["publicInformation"]:
                obj_colors = supply_obj["publicInformation"]["colors"]
            elif "colors" in supply_obj:
                obj_colors = supply_obj["colors"]
            
            # If colors list exists and has > 1 item, it's a multi-color supply (e.g. printhead) -> Exclude
            if isinstance(obj_colors, list) and len(obj_colors) > 1:
                return False
                
            # 2. Check if it matches requested colors
            # Gather all color indicators
            indicators = []
            if isinstance(obj_colors, list): indicators.extend(obj_colors)
            
            if "publicInformation" in supply_obj:
                indicators.append(supply_obj["publicInformation"].get("supplyColorCode"))
            indicators.append(supply_obj.get("supplyColorCode"))
            
            for field in indicators:
                if not field: continue
                field_str = str(field).lower()
                
                # If field implies multiple colors (e.g. "CMYK"), exclude
                if len(field_str) > 2 and "c" in field_str and "m" in field_str: 
                    return False
                
                for c in colors:
                    target = c.lower()
                    # Check match: "m" vs "magenta"
                    if target == "magenta" and ("m" == field_str or "magenta" in field_str): return True
                    if target == "cyan" and ("c" == field_str or "cyan" in field_str): return True
                    if target == "yellow" and ("y" == field_str or "yellow" in field_str): return True
                    if target == "black" and ("k" == field_str or "black" in field_str): return True
            return False

        if isinstance(data, dict):
            if "suppliesList" in data and isinstance(data["suppliesList"], list):
                # Public format
                filtered_list = [item for item in data["suppliesList"] if is_valid_supply(item)]
                data["suppliesList"] = filtered_list
            else:
                # Private format (dict keys)
                keys_to_remove = []
                for key, value in data.items():
                    if key == "version": continue
                    if isinstance(value, dict):
                        if not is_valid_supply(value):
                            keys_to_remove.append(key)
                
                for k in keys_to_remove:
                    del data[k]
                    
        return data

    def _process_telemetry(self, file_paths):
        results = []
        for path in file_paths:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        # Parse and check color match
                        try:
                            data = json.loads(content)
                            # Pretty print with standard 4-space indent
                            pretty = json.dumps(data, indent=4)
                            # Add tab prefix to each line
                            tab_prefixed = '\t' + pretty.replace('\n', '\n\t')
                            results.append(tab_prefixed)
                        except json.JSONDecodeError:
                            # If not valid JSON, skip it
                            pass
            except:
                pass
        return results
