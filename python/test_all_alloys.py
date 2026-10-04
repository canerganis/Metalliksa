import os
import itertools
import pandas as pd
from lpbf_thermal_solver import calculate_meltpool_physics
from lpbf_defect_diagnostics import defect_diagnostics
from murakami_fatigue_screening import murakami_fatigue_limit_MPa
from phase9_surrogate import train_surrogate, predict_surrogate
from phase10_industrial import run_industrial_fatigue_analysis

def generate_316L_data():
    mat = "316L SS"
    powers = [100, 150, 200, 250, 300, 350, 400, 450]
    speeds = [400, 600, 800, 1000, 1200, 1400, 1600, 1800, 2000]
    hatch_spacings = [70, 90, 110]
    layers = [30, 40, 50]

    data = []
    print("Generating 316L SS physical dataset...")
    
    for P, V, H, L in itertools.product(powers, speeds, hatch_spacings, layers):
        try:
            res = calculate_meltpool_physics(
                material_name=mat,
                laser_power_W=P,
                scan_speed_mm_s=V,
                beam_diameter_um=80.0,
                preheat_temp_C=25.0,
                layer_thickness_um=L,
                hatch_spacing_um=H
            )
            
            geom = res.get("meltPoolGeometry", {})
            w = geom.get("width_um", 0)
            d = geom.get("depth_um", 0)
            length = geom.get("length_um", 0)
            cooling_rate = res.get("thermal", {}).get("coolingRate_K_s", 0)
            
            if w > 0 and d > 0:
                diag = defect_diagnostics(w, d, length, H, L, aggregate=False)
                lof_risk = diag.get("lackOfFusion", {}).get("riskScreened", "unknown")
                keyhole_ratio = diag.get("keyhole", {}).get("depthToWidth", 0)
                
                if lof_risk == "high":
                    defect_size_um = 60.0
                elif lof_risk == "moderate":
                    defect_size_um = 30.0
                else:
                    if keyhole_ratio is not None and keyhole_ratio > 0.6:
                        defect_size_um = 40.0
                    else:
                        defect_size_um = 5.0
                        
                hv = 215.0 # From fatigue DB for 316L SS
                fatigue = murakami_fatigue_limit_MPa(defect_size_um, hv, "internal")
                
                data.append({
                    "Material": mat, "Power_W": P, "Speed_mm_s": V, "Hatch_um": H,
                    "Layer_um": L, "Width_um": w, "Depth_um": d, "Length_um": length,
                    "CoolingRate_K_s": cooling_rate, "LOF_Risk": lof_risk,
                    "Keyhole_Ratio": keyhole_ratio, "DefectSize_um": defect_size_um,
                    "FatigueLimit_MPa": fatigue
                })
        except Exception as e:
            pass

    df_new = pd.DataFrame(data)
    csv_path = "../data/synthetic_process_map.csv"
    if os.path.exists(csv_path):
        df_old = pd.read_csv(csv_path)
        df_old = df_old[df_old["Material"] != mat]
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
    else:
        df_combined = df_new
        
    df_combined.to_csv(csv_path, index=False)
    print(f"Added {len(df_new)} rows for 316L SS. Total dataset size: {len(df_combined)}")

def test_all_alloys():
    alloys = ["IN718", "Ti-6Al-4V", "AlSi10Mg", "316L SS"]
    
    # Common process parameters for comparison
    P = 250.0  # W
    V = 1000.0 # mm/s
    
    print("\n" + "="*80)
    print(f"COMPARATIVE ALLOY TEST @ P={P}W, V={V}mm/s, Hatch=100um, Layer=30um")
    print("="*80)
    
    for alloy in alloys:
        print(f"\n[{alloy.upper()}]")
        try:
            # 1. Run Industrial Fatigue Analysis (which uses the AI surrogate under the hood)
            res = run_industrial_fatigue_analysis(alloy, P, V, layer_thickness_um=30.0, hatch_spacing_um=100.0)
            
            mp = res.get("AI_Meltpool", {})
            fatigue = res.get("Certification_Limits", {})
            gumbel = res.get("Defect_Simulation", {})
            
            print(f"  -> Meltpool: Width=~{mp.get('Mean_Depth_um', 0)*1.1:.1f}um | Depth={mp.get('Mean_Depth_um', 0):.1f}um (±{mp.get('Uncertainty_Std_um', 0):.1f})")
            largest = gumbel.get('Gumbel_Predicted_Largest_Defect_um')
            design = fatigue.get('Design_Limit_MPa')
            print(f"  -> Largest Expected Defect: {'unavailable (no defect simulated)' if largest is None else f'{largest:.1f} um'}")
            print(f"  -> Design Limit (fixed 0.85 knockdown, illustrative): {'unavailable' if design is None else f'{design:.1f} MPa'}")
        except Exception as e:
            print(f"  -> Failed to analyze: {e}")

if __name__ == "__main__":
    generate_316L_data()
    print("Training surrogate for 316L SS...")
    train_surrogate("316L SS", 200)
    test_all_alloys()
