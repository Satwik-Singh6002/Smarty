"""
CAD Agent using OpenRouter API
Generates 3D CAD models using build123d library via AI code generation.
Enhanced for high-identifiability, recognizable silhouettes, boolean features, and robust execution.
"""
import os
import re
import json
import asyncio
import subprocess
import sys
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

from openrouter_client import OpenRouterClient

load_dotenv()


class CadAgent:
    """
    CAD Agent that uses OpenRouter to generate build123d Python scripts
    for 3D model generation.
    """
    
    def __init__(self, on_thought=None, on_status=None):
        self.client = OpenRouterClient()
        self.on_thought = on_thought  # Callback for streaming thoughts 
        self.on_status = on_status  # Callback for retry status info
        
        self.system_instruction = """You are a Master 3D CAD Engineer using Python and the `build123d` library.
Your objective is to generate detailed, aesthetically pleasing, structurally sound, and INSTANTLY RECOGNIZABLE 3D models based on user requests across all domains: vehicles, architecture (houses, buildings), nature (trees, plants), animals/characters, and everyday objects.

=============================
CORE PRINCIPLES OF RECOGNIZABILITY
=============================
A 3D model is recognizable when its silhouette, proportions, negative space, and signature details match the real-world or iconic representation of the object:

1. SILHOUETTE & ANATOMY:
   - NEVER output an oversimplified single-box or single-cylinder blob.
   - Deconstruct the object into its iconic components:
     * VEHICLES (Car, Truck, Plane): Chassis + elevated cabin/windshield + recessed wheel arches + 4 wheels with rim hubs + front bumper/headlights + spoiler.
     * ARCHITECTURE (House, Building): Foundation slab + walls + recessed front door (Mode.SUBTRACT) + recessed window cutouts (Mode.SUBTRACT) + pitched gable roof / crown + chimney / antenna.
     * NATURE (Tree, Plant): Contoured trunk with flared roots + tiered multi-level foliage canopy (conical or spherical overlapping clusters).
     * ANIMALS (Dog, Cat, Bear, Bird): Proportioned body/torso + head/snout + ears + 4 legs/paws + tail + facial features.
     * OBJECTS (Mug, Stand, Tool, Furniture): Base + core body + ergonomic cuts/slots + handles + negative hollow cavities.

2. NEGATIVE SPACE & BOOLEAN OPERATIONS (Mode.SUBTRACT):
   - Real objects are defined by their cuts, cavities, slots, and openings.
   - Use `mode=Mode.SUBTRACT` inside `with BuildPart() as p:` to carve out:
     * Hollow interiors for cups, bowls, vases, and boxes.
     * Recessed wheel arches/wells for cars, trucks, and vehicles.
     * Recessed door and window openings for houses and buildings.
     * Cable routing slots and charging pass-throughs for stands.
     * Visor slits, windows, fullers, panel grooves, and mounting holes.
   - Subtractive shapes must cleanly intersect the target solid.

3. SYMMETRICAL REPETITION WITH LOCATIONS:
   - Use `with Locations([...]):` to position symmetrical components cleanly in one statement:
     * 4 wheels, 4 legs, or 4 window columns: `with Locations((-x, y, z), (x, y, z), (-x, -y, z), (x, -y, z)):`
     * Left and right headlights, eyes, ears, wings, or arms: `with Locations((x, -y, z), (x, y, z)):`

4. SCALE & PROPORTIONS:
   - Design at millimeter dimensions suitable for 3D printing and desktop inspection (generally 30mm to 120mm overall).
   - Keep minimum wall thickness between 2.0mm and 4.0mm so objects are solid and printable.
   - Center the overall model at or near (0, 0, 0).

5. SOLID INTEGRITY:
   - All positive features MUST physically touch or overlap adjacent parts so they fuse into a single manifold solid.
   - Always assign: `result_part = p.part if p.part is not None else Compound(p.solids())`
   - Always finish with: `export_stl(result_part, 'output.stl')`

=============================
BUILD123D API RULES & CONVENTIONS
=============================
- Import: `from build123d import *`
- Outer context: ALWAYS use `with BuildPart() as p:` as the main builder context.
- Core 3D Primitive Signatures:
  * Box(length_x, width_y, height_z, rotation=(rx,ry,rz), align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.ADD)
  * Cylinder(radius, height, rotation=(rx,ry,rz), align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.ADD)
  * Sphere(radius, rotation=(rx,ry,rz), align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.ADD)
  * Cone(bottom_radius, top_radius, height, rotation=(rx,ry,rz), align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.ADD)
    * Pointed cone: MUST provide 3 numeric arguments: Cone(bottom_radius, 0, height)
  * Torus(major_radius, minor_radius, rotation=(rx,ry,rz), align=(Align.CENTER, Align.CENTER, Align.CENTER), mode=Mode.ADD)
- Alignments:
  * ONLY use `Align.MIN`, `Align.CENTER`, or `Align.MAX`. (Never use non-existent enums like Align.BOTTOM or Align.TOP).
- Rotation:
  * Standard Euler angles in degrees: e.g. `rotation=(90, 0, 0)` to rotate a cylinder to be horizontal.
- 2D Sketch Profiles in 3D:
  * You can create extruded sketches for roofs, wedges, or custom profiles:
    ```python
    with Locations((0, 0, z)):
        with BuildSketch(Plane.XZ) as s:
            Triangle(a=width, b=height, c=height)
        extrude(amount=depth, both=True)
    ```
- Fillets & Chamfers:
  * Only apply small conservative values (0.5mm to 1.5mm) on specific edge selections (e.g. `fillet(p.edges().filter_by(Axis.Z), radius=1.0)`).
  * If unsure, omit fillets to ensure 100% build reliability without kernel errors.

=============================
REFERENCE EXAMPLES BY DOMAIN
=============================

--- Example 1: Detailed Vehicle (Car) ---
```python
from build123d import *

with BuildPart() as p:
    # 1. Main lower chassis
    Box(70, 32, 14, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    
    # 2. Elevated cabin with rear-slanted profile
    with Locations((-5, 0, 13)):
        Box(38, 26, 12, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    
    # 3. Cutout wheel arches (subtraction)
    with Locations((-18, 16, -5), (18, 16, -5), (-18, -16, -5), (18, -16, -5)):
        Cylinder(radius=9.5, height=8, rotation=(90, 0, 0), mode=Mode.SUBTRACT)
    
    # 4. Wheels with central rim hubs
    with Locations((-18, 16.5, -5), (18, 16.5, -5), (-18, -16.5, -5), (18, -16.5, -5)):
        Cylinder(radius=8, height=5, rotation=(90, 0, 0))
        Cylinder(radius=3.5, height=6.5, rotation=(90, 0, 0))
        
    # 5. Front bumper & headlights
    with Locations((35, 0, -4)):
        Box(3, 28, 5)
    with Locations((35, -9, 1), (35, 9, 1)):
        Cylinder(radius=3, height=2, rotation=(0, 90, 0))

result_part = p.part if p.part is not None else Compound(p.solids())
export_stl(result_part, 'output.stl')
```

--- Example 2: Architecture (House with Gable Roof, Door & Windows) ---
```python
from build123d import *

with BuildPart() as p:
    # 1. Foundation slab
    Box(60, 50, 4, align=(Align.CENTER, Align.CENTER, Align.MIN))
    
    # 2. Main house walls
    with Locations((0, 0, 4)):
        Box(52, 42, 28, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 3. Recessed front door (subtraction)
    with Locations((0, -21, 4)):
        Box(10, 4, 18, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 4. Recessed windows on front and sides (subtraction)
    with Locations((-16, -21, 14), (16, -21, 14)):
        Box(10, 4, 10, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.CENTER))
    with Locations((-26, 0, 14), (26, 0, 14)):
        Box(4, 12, 10, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        
    # 5. Pitched Gable Roof
    with Locations((0, 0, 32)):
        with BuildSketch(Plane.XZ) as s:
            Triangle(a=58, b=41, c=41)
        extrude(amount=24, both=True)
        
    # 6. Chimney on roof with flue cutout
    with Locations((16, 8, 36)):
        Box(8, 8, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
        with Locations((0, 0, 18)):
            Box(6, 6, 4, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.MIN))

result_part = p.part if p.part is not None else Compound(p.solids())
export_stl(result_part, 'output.stl')
```

--- Example 3: Nature (Tree with Root Flares & Tiered Canopy) ---
```python
from build123d import *

with BuildPart() as p:
    # 1. Main trunk
    Cone(bottom_radius=8, top_radius=5, height=35, align=(Align.CENTER, Align.CENTER, Align.MIN))
    
    # 2. Root flares at base
    with Locations((0, 0, 0)):
        for angle in [0, 90, 180, 270]:
            Box(20, 4, 6, rotation=(0, 0, angle), align=(Align.CENTER, Align.CENTER, Align.MIN))
            
    # 3. Tiered foliage canopy (overlapping conical clusters)
    with Locations((0, 0, 25)):
        Cone(bottom_radius=26, top_radius=2, height=22, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with Locations((0, 0, 38)):
        Cone(bottom_radius=20, top_radius=2, height=20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with Locations((0, 0, 50)):
        Cone(bottom_radius=14, top_radius=0, height=18, align=(Align.CENTER, Align.CENTER, Align.MIN))

result_part = p.part if p.part is not None else Compound(p.solids())
export_stl(result_part, 'output.stl')
```

--- Example 4: Architecture (Skyscraper / Multi-Story Building) ---
```python
from build123d import *

with BuildPart() as p:
    # 1. Base podium & entrance plaza
    Box(50, 40, 8, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with Locations((0, -20, 0)):
        Box(16, 6, 6, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 2. Tower core shaft
    with Locations((0, 0, 8)):
        Box(40, 32, 70, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 3. Setback upper crown
    with Locations((0, 0, 78)):
        Box(30, 24, 25, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 4. Multi-story window grooves (subtraction)
    for z in [20, 35, 50, 65]:
        with Locations((0, 0, z)):
            Box(42, 34, 4, mode=Mode.SUBTRACT, align=(Align.CENTER, Align.CENTER, Align.CENTER))
            
    # 5. Rooftop spire / antenna
    with Locations((0, 0, 103)):
        Cylinder(radius=2, height=20, align=(Align.CENTER, Align.CENTER, Align.MIN))
        Sphere(radius=3, align=(Align.CENTER, Align.CENTER, Align.MIN))

result_part = p.part if p.part is not None else Compound(p.solids())
export_stl(result_part, 'output.stl')
```

--- Example 5: Animal / Creature (Stylized Dog / Quadruped) ---
```python
from build123d import *

with BuildPart() as p:
    # 1. Torso body (lying horizontally)
    Cylinder(radius=11, height=36, rotation=(0, 90, 0), align=(Align.CENTER, Align.CENTER, Align.CENTER))
    
    # 2. Chest & neck spacer
    with Locations((16, 0, 6)):
        Sphere(radius=10)
        
    # 3. Head with snout/muzzle
    with Locations((22, 0, 14)):
        Sphere(radius=9)
    # Snout
    with Locations((30, 0, 12)):
        Box(8, 7, 6, align=(Align.CENTER, Align.CENTER, Align.CENTER))
        
    # 4. Pointed/folded ears
    with Locations((20, -7, 21), (20, 7, 21)):
        Cone(bottom_radius=3, top_radius=0, height=8, align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 5. Four sturdy legs
    with Locations((12, -8, -10), (12, 8, -10), (-12, -8, -10), (-12, 8, -10)):
        Cylinder(radius=3.5, height=14, align=(Align.CENTER, Align.CENTER, Align.MAX))
        with Locations((2, 0, -14)):
            Box(9, 6, 4, align=(Align.CENTER, Align.CENTER, Align.CENTER))
            
    # 6. Tail wagging upward
    with Locations((-16, 0, 5)):
        Cylinder(radius=2.5, height=16, rotation=(0, -45, 0), align=(Align.CENTER, Align.CENTER, Align.MIN))
        
    # 7. Eyes (small spheres)
    with Locations((28, -4, 16), (28, 4, 16)):
        Sphere(radius=1.5)

result_part = p.part if p.part is not None else Compound(p.solids())
export_stl(result_part, 'output.stl')
```

IMPORTANT: Always output the complete, runnable Python script inside a single ```python ``` block."""

    def _sanitize_and_prepare_code(self, raw_code: str, output_stl: str) -> str:
        """
        Sanitizes generated python code:
        - Ensures imports exist
        - Injects safe forward-slash STL export path (immune to Windows unicodeescape bugs)
        - Ensures Compound fallback for non-manifold multi-body shapes
        - Ensures export_stl is properly called
        """
        code = raw_code.strip()
        safe_output_path = output_stl.replace("\\", "/")
        
        # Ensure build123d import
        if "from build123d" not in code and "import build123d" not in code:
            code = "from build123d import *\n" + code
            
        # Replace output.stl variations with safe path
        if re.search(r"['\"](?:\./)?output\.stl['\"]", code):
            code = re.sub(
                r"['\"](?:\./)?output\.stl['\"]",
                lambda _: f"'{safe_output_path}'",
                code
            )
        elif "export_stl" in code:
            code = re.sub(
                r"export_stl\s*\(\s*([^,]+)\s*,\s*['\"][^'\"]+['\"]\s*\)",
                lambda m: f"export_stl({m.group(1)}, '{safe_output_path}')",
                code
            )
        else:
            # export_stl missing altogether: append it
            code += f"\nresult_part = p.part if getattr(p, 'part', None) is not None else Compound(p.solids())\nexport_stl(result_part, '{safe_output_path}')\n"
            
        # Ensure result_part = p.part handles Compound fallback
        code = re.sub(
            r"result_part\s*=\s*p\.part(?!\s*if)",
            "result_part = p.part if getattr(p, 'part', None) is not None else Compound(p.solids())",
            code
        )
        
        return code

    async def _execute_script(self, script_path: str, code: str) -> tuple[int, str, str]:
        """
        Executes the python CAD script with automatic fillet/chamfer error recovery.
        Returns: (returncode, stdout, stderr)
        """
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)
            
        try:
            proc = await asyncio.to_thread(
                subprocess.run,
                [sys.executable, script_path],
                capture_output=True,
                text=True
            )
            stdout, stderr = proc.stdout, proc.stderr
        except Exception as e:
            return 1, "", str(e)
            
        # Auto-repair: If script failed due to fillet/chamfer kernel error, remove those calls and retry immediately
        if proc.returncode != 0 and any(err in stderr for err in ["fillet", "chamfer", "Standard_ConstructionError", "BRep_API", "ChFi3d", "StdFail"]):
            print("[CadAgent DEBUG] [AUTO-REPAIR] Fillet/chamfer error detected. Safely removing and re-testing...")
            if self.on_thought:
                self.on_thought("Auto-repairing: safely removing problematic fillet/chamfer geometry...\n")
                
            repaired_code = re.sub(
                r'^[ \t]*(?:[a-zA-Z_0-9\.]+\s*=\s*)?(?:fillet|chamfer)\s*\(.*?\)[ \t]*$',
                r'# \g<0> # auto-removed for geometry safety',
                code,
                flags=re.MULTILINE
            )
            if repaired_code != code:
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(repaired_code)
                try:
                    proc_repair = await asyncio.to_thread(
                        subprocess.run,
                        [sys.executable, script_path],
                        capture_output=True,
                        text=True
                    )
                    if proc_repair.returncode == 0:
                        print("[CadAgent DEBUG] [AUTO-REPAIR] Success! Geometry compiled cleanly.")
                        if self.on_thought:
                            self.on_thought("Auto-repair successful! Geometry compiled cleanly.\n")
                        return proc_repair.returncode, proc_repair.stdout, proc_repair.stderr
                    else:
                        stdout, stderr = proc_repair.stdout, proc_repair.stderr
                except Exception:
                    pass
                    
        return proc.returncode, stdout, stderr

    async def generate_prototype(self, prompt: str, output_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Generates 3D geometry by asking AI for a script, then running it LOCALLY.
        Enhanced for high recognizability, boolean subtractions, and robust recovery.
        """
        print(f"[CadAgent DEBUG] [START] Generation started for: '{prompt}'")
        
        try:
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                work_dir = output_dir
            else:
                import tempfile
                work_dir = tempfile.gettempdir()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_stl = os.path.join(work_dir, f"output_{timestamp}.stl")
            script_path = os.path.join(work_dir, "current_design.py")

            if self.on_thought:
                self.on_thought(f"Deconstructing '{prompt}' into iconic 3D features and negative space...\n")

            user_prompt = f"""You are a master 3D CAD designer using `build123d`.
Create an instantly recognizable, detailed, and proportioned 3D CAD model of: '{prompt}'.

Key Design Instructions:
1. IDENTIFIABILITY & RECOGNIZABILITY:
   - Do NOT create a single vague primitive blob.
   - Deconstruct '{prompt}' into its iconic visual features (silhouette, primary body, secondary structural parts, and signature accents).
   - Use `mode=Mode.SUBTRACT` for negative space: carve out hollows, wheel arches, windows, cavities, grooves, or slots.
2. PROPORTIONS & SCALE:
   - Model at reasonable millimeter dimensions (typically 30mm - 120mm overall bounding box).
   - Center the model near (0, 0, 0).
3. SOLID INTEGRITY:
   - Ensure all positive components intersect and fuse cleanly into a single solid part.
4. EXPORT:
   - Assign the final solid: `result_part = p.part if p.part is not None else Compound(p.solids())`
   - Export using: `export_stl(result_part, 'output.stl')`

Return the complete python script inside a ```python ``` code block."""

            max_retries = 3
            messages = [{"role": "user", "content": user_prompt}]
            
            for attempt in range(max_retries):
                print(f"[CadAgent DEBUG] Attempt {attempt + 1}/{max_retries}")
                
                if self.on_status:
                    self.on_status({
                        "status": "generating" if attempt == 0 else "retrying",
                        "attempt": attempt + 1,
                        "max_attempts": max_retries,
                        "error": None
                    })
                
                if self.on_thought and attempt > 0:
                    self.on_thought(f"Refining CAD model script (Attempt {attempt + 1}/{max_retries})...\n")

                # 1. Ask OpenRouter for the code
                response = await self.client.chat(
                    messages=messages,
                    system_instruction=self.system_instruction,
                    temperature=0.6,
                    max_tokens=4096
                )
                
                raw_content = response.get("content", "")
                if not raw_content:
                    print("[CadAgent DEBUG] [ERR] Empty response from model.")
                    return None

                # 2. Extract Code Block
                code_match = re.search(r'```(?:python|py)?\s*(.*?)\s*```', raw_content, re.DOTALL)
                if code_match:
                    code = code_match.group(1).strip()
                elif "build123d" in raw_content or "from build123d" in raw_content:
                    code = raw_content.strip()
                else:
                    print("[CadAgent DEBUG] [ERR] Could not extract python code.")
                    return None

                # 3. Sanitize and prepare code
                code_with_path = self._sanitize_and_prepare_code(code, output_stl)
                print(f"[CadAgent DEBUG] [EXEC] Running local script: {script_path}")
                
                if self.on_thought:
                    self.on_thought("Compiling 3D CSG geometry with local build123d engine...\n")

                # 4. Execute Locally with auto-repair
                returncode, stdout, stderr = await self._execute_script(script_path, code_with_path)
                
                if returncode != 0:
                    error_msg = stderr
                    error_lines = error_msg.strip().split('\n')
                    short_error = error_lines[-1][:100] if error_lines else "Unknown error"
                    print(f"[CadAgent DEBUG] [ERR] Script Execution Failed:\n{error_msg}")
                    
                    if self.on_status:
                        self.on_status({
                            "status": "retrying",
                            "attempt": attempt + 1,
                            "max_attempts": max_retries,
                            "error": short_error
                        })
                    
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": f"""The Python script failed with this error:
{error_msg}

Please fix the error. Return the full corrected script inside a ```python ``` block.
Ensure you export to 'output.stl' and assign `result_part = p.part if p.part is not None else Compound(p.solids())`.
Original request: {prompt}"""})
                    continue

                print(f"[CadAgent DEBUG] [OK] Script executed successfully.")
                
                # 5. Read Output
                if os.path.exists(output_stl):
                    print(f"[CadAgent DEBUG] [file] '{output_stl}' found.")
                    with open(output_stl, "rb") as f:
                        stl_data = f.read()
                        
                    b64_stl = base64.b64encode(stl_data).decode('utf-8')
                    
                    if self.on_thought:
                        self.on_thought("Design compiled successfully! 3D model loaded.\n")
                        
                    return {
                        "format": "stl",
                        "data": b64_stl,
                        "file_path": output_stl
                    }
                else:
                    print(f"[CadAgent DEBUG] [ERR] '{output_stl}' was not generated.")
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": f"The script executed but '{output_stl}' was not found. Make sure you call `export_stl(result_part, 'output.stl')` at the end."})
                    continue

            print("[CadAgent DEBUG] [ERR] All attempts failed.")
            if self.on_status:
                self.on_status({
                    "status": "failed",
                    "attempt": max_retries,
                    "max_attempts": max_retries,
                    "error": "All generation attempts failed"
                })
            return None

        except Exception as e:
            print(f"CadAgent Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def iterate_prototype(self, prompt: str, output_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Iterates on the existing design by reading 'current_design.py' and applying changes.
        """
        print(f"[CadAgent DEBUG] [START] Iteration started for: '{prompt}'")
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            work_dir = output_dir
        else:
            import tempfile
            work_dir = tempfile.gettempdir()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        script_path = os.path.join(work_dir, "current_design.py")
        output_stl = os.path.join(work_dir, f"output_{timestamp}.stl")
        
        existing_code = ""
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as f:
                existing_code = f.read()
            
            # Sanitize existing code: replace any hardcoded paths with 'output.stl'
            existing_code = re.sub(
                r"['\"][^'\"]*output[^'\"]*\.stl['\"]",
                "'output.stl'",
                existing_code
            )
        else:
            print("[CadAgent DEBUG] [WARN] No existing script found. Falling back to fresh generation.")
            return await self.generate_prototype(prompt, output_dir)

        if self.on_thought:
            self.on_thought(f"Iterating design: applying '{prompt}' to existing CAD model...\n")

        try:
            max_retries = 3
            messages = [{"role": "user", "content": f"""You are iterating on an existing 3D model script using `build123d`.

Current Python Code:
```python
{existing_code}
```

User Iteration Request: '{prompt}'

Task Requirements:
1. Carefully modify the existing script to incorporate the requested changes (e.g. adjust dimensions, add/remove features, enhance details).
2. Maintain the recognizable silhouette, proportions, and boolean subtractive features (Mode.SUBTRACT) already established in the design.
3. Ensure all newly added positive features intersect and fuse cleanly into the solid.
4. Assign the final solid: `result_part = p.part if p.part is not None else Compound(p.solids())`
5. Export using: `export_stl(result_part, 'output.stl')`

Return the full updated Python script inside a single ```python ``` code block."""}]
            
            for attempt in range(max_retries):
                print(f"[CadAgent DEBUG] Iteration Attempt {attempt + 1}/{max_retries}")
                
                if self.on_status:
                    self.on_status({
                        "status": "generating" if attempt == 0 else "retrying",
                        "attempt": attempt + 1,
                        "max_attempts": max_retries,
                        "error": None
                    })
                
                response = await self.client.chat(
                    messages=messages,
                    system_instruction=self.system_instruction,
                    temperature=0.6,
                    max_tokens=4096
                )
                
                raw_content = response.get("content", "")
                if not raw_content:
                    print("[CadAgent DEBUG] [ERR] Empty response from model.")
                    return None

                code_match = re.search(r'```(?:python|py)?\s*(.*?)\s*```', raw_content, re.DOTALL)
                if code_match:
                    code = code_match.group(1).strip()
                elif "build123d" in raw_content or "from build123d" in raw_content:
                    code = raw_content.strip()
                else:
                    print("[CadAgent DEBUG] [ERR] Could not extract python code.")
                    return None

                code_with_path = self._sanitize_and_prepare_code(code, output_stl)
                print(f"[CadAgent DEBUG] [EXEC] Running local script: {script_path}")
                
                if self.on_thought:
                    self.on_thought("Compiling updated CAD geometry with local build123d engine...\n")

                returncode, stdout, stderr = await self._execute_script(script_path, code_with_path)
                
                if returncode != 0:
                    error_msg = stderr
                    error_lines = error_msg.strip().split('\n')
                    short_error = error_lines[-1][:100] if error_lines else "Unknown error"
                    print(f"[CadAgent DEBUG] [ERR] Script Execution Failed:\n{error_msg}")
                    
                    if self.on_status:
                        self.on_status({
                            "status": "retrying",
                            "attempt": attempt + 1,
                            "max_attempts": max_retries,
                            "error": short_error
                        })
                    
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": f"""The updated Python script failed with this error:
{error_msg}

Please fix the error and return the full corrected script inside a ```python ``` block.
Ensure you export to 'output.stl' and assign `result_part = p.part if p.part is not None else Compound(p.solids())`."""})
                    continue

                print(f"[CadAgent DEBUG] [OK] Script executed successfully.")
                
                if os.path.exists(output_stl):
                    print(f"[CadAgent DEBUG] [file] '{output_stl}' found.")
                    with open(output_stl, "rb") as f:
                        stl_data = f.read()
                        
                    b64_stl = base64.b64encode(stl_data).decode('utf-8')
                    
                    if self.on_thought:
                        self.on_thought("Iterated design compiled successfully! 3D model updated.\n")
                        
                    return {
                        "format": "stl",
                        "data": b64_stl,
                        "file_path": output_stl
                    }
                else:
                    print(f"[CadAgent DEBUG] [ERR] '{output_stl}' was not generated.")
                    messages.append({"role": "assistant", "content": raw_content})
                    messages.append({"role": "user", "content": f"The script executed successfully but '{output_stl}' was not found. Ensure you call `export_stl(result_part, 'output.stl')`."})
                    continue

            print("[CadAgent DEBUG] [ERR] All attempts failed.")
            if self.on_status:
                self.on_status({
                    "status": "failed",
                    "attempt": max_retries,
                    "max_attempts": max_retries,
                    "error": "All iteration attempts failed"
                })
            return None

        except Exception as e:
            print(f"CadAgent Error: {e}")
            import traceback
            traceback.print_exc()
            return None
