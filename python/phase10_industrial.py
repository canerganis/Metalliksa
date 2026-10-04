import os
import json
import numpy as np
from typing import Dict, Any

import alloy_registry
from phase9_surrogate import predict_surrogate
from murakami_fatigue_screening import ALLOY_HV_DEFAULTS, evaluate_murakami_block, gumbel_fit_maxima

# fx-icme (backlog lane 9): honesty labels. The defects are SAMPLED from a normal distribution of
# the surrogate melt-pool depth with rough lack-of-fusion / keyhole rules; they are not measured.
MODEL_STATUS = "illustrative"
MODEL_STATUS_NOTE = (
    "Illustrative screening estimate. Defect sizes are sampled (5000 draws, fixed seed 42) from a "
    "normal distribution around the surrogate melt-pool depth with rough lack-of-fusion "
    "(depth < 1.5 x layer) and keyhole (depth > 4 x layer) rules; they are not measured defects. "
    "The fatigue limit is the Murakami sqrt(area) screening limit and the design limit is a fixed "
    "0.85 knockdown of it, not a statistical survival bound. When the sampled population contains "
    "no defect, no defect size is invented and the fatigue limits are unavailable. The hardness comes "
    "from a short screening table (Ti-6Al-4V, 316L, AlSi10Mg, IN718) reached by exact alloy alias; for "
    "any other alloy the fatigue limits are unavailable (no hardness is assumed)."
)
NO_HARDNESS_STATUS = (
    "unavailable: no hardness for alloy; the Murakami limit needs a Vickers hardness and this alloy does not "
    "resolve (exact registry alias) to an alloy with a tabulated screening hardness, so none is assumed"
)
DESIGN_LIMIT_KNOCKDOWN = 0.85


def table_hardness_alloy_id(alloy_name):
    """Registry id when ``alloy_name`` resolves (exact name/alias, no substring match) to an alloy that has a
    screening hardness in murakami_fatigue_screening.ALLOY_HV_DEFAULTS; otherwise None (no generic 350 HV)."""
    try:
        alloy_id = alloy_registry.resolve_alloy_id(alloy_name)
    except alloy_registry.AlloyRegistryError:
        return None
    return alloy_id if alloy_id in ALLOY_HV_DEFAULTS else None

DESIGN_LIMIT_BASIS = (
    "illustrative: fixed 0.85 knockdown of the Murakami internal-defect screening limit; "
    "not a statistical 99 % survival bound"
)
NO_DEFECT_STATUS = (
    "unavailable: the sampled population contains no defect above 5 um, and a Murakami sqrt(area) "
    "limit needs a defect size; none is assumed"
)

def run_industrial_fatigue_analysis(alloy_name: str, laser_power_W: float, scan_speed_mm_s: float, 
                                    layer_thickness_um: float = 30.0, hatch_spacing_um: float = 100.0) -> Dict[str, Any]:
    
    # 1. AI Surrogate'ten Eriyik Havuzu Tahmini (Milisaniye)
    # T0 (Preheat) = 25 C olarak sabitliyoruz.
    surrogate_res = predict_surrogate(alloy_name, laser_power_W, scan_speed_mm_s, 25.0)
        
    mean_depth = surrogate_res["depth_um"]
    std_depth = surrogate_res["error_budget"]["depth_std_um"]
    
    # 2. Monte Carlo Hata (Defect) Simülasyonu
    # Parçanın milyonlarca track'ten oluştuğunu farz edip 5000 kritik bölge örneği alıyoruz.
    np.random.seed(42)
    mc_samples = 5000
    simulated_depths = np.random.normal(loc=mean_depth, scale=max(std_depth, 2.0), size=mc_samples)
    
    defect_sizes_um = []
    
    # Kaba bir fiziksel Hata (Defect) Kuralı:
    # Eriyik derinliği, katman kalınlığını (layer_thickness) belirli bir miktar geçemezse Lack of Fusion (LoF) oluşur.
    lof_threshold = layer_thickness_um * 1.5 
    
    for d in simulated_depths:
        if d < lof_threshold:
            # Lack of fusion defect size (karekök alan yaklaşımı)
            defect_size = (lof_threshold - d) * 2.0
            if defect_size > 5.0:
                defect_sizes_um.append(defect_size)
        elif d > (layer_thickness_um * 4.0):
            # Keyhole gözenekliliği
            defect_size = d * 0.15
            if defect_size > 5.0:
                defect_sizes_um.append(defect_size)

    if not defect_sizes_um:
        # Hata oluşmadıysa temsili hata UYDURULMAZ (önceden 10 um enjekte ediliyordu): Murakami
        # sqrt(area) sınırı bir hata boyutu gerektirir; sonuç 'unavailable' olarak raporlanır.
        return {
            "modelStatus": MODEL_STATUS,
            "modelStatusNote": MODEL_STATUS_NOTE,
            "AI_Meltpool": {
                "Mean_Depth_um": round(mean_depth, 2),
                "Uncertainty_Std_um": round(std_depth, 2),
                "Confidence_Pct": round(surrogate_res["error_budget"]["confidence_pct"], 1)
            },
            "Defect_Simulation": {
                "Total_Defects_Found": 0,
                "Max_Simulated_Defect_um": None,
                "Gumbel_Predicted_Largest_Defect_um": None,
                "Status": NO_DEFECT_STATUS
            },
            "Certification_Limits": {
                "Expected_Fatigue_Limit_MPa": None,
                "Design_Limit_MPa": None,
                "Hardness_Used_HV": None,
                "Status": NO_DEFECT_STATUS
            }
        }

    # Sertlik: yalnızca kayıt defterinde tam eşleşen ve tablosu olan alaşımlar için. Aksi halde genel 350 HV
    # UYDURULMAZ (önceden alloy_name.lower() eşleşmezse 350 HV kullanılıyordu; 316L için limitler +%42 abartılıyordu).
    hardness_alloy_id = table_hardness_alloy_id(alloy_name)
    if hardness_alloy_id is None:
        gumbel = gumbel_fit_maxima(defect_sizes_um)
        largest = gumbel["characteristicLargest_um"] if gumbel else max(defect_sizes_um)
        return {
            "modelStatus": MODEL_STATUS,
            "modelStatusNote": MODEL_STATUS_NOTE,
            "AI_Meltpool": {
                "Mean_Depth_um": round(mean_depth, 2),
                "Uncertainty_Std_um": round(std_depth, 2),
                "Confidence_Pct": round(surrogate_res["error_budget"]["confidence_pct"], 1)
            },
            "Defect_Simulation": {
                "Total_Defects_Found": len(defect_sizes_um),
                "Max_Simulated_Defect_um": round(max(defect_sizes_um), 2),
                "Gumbel_Predicted_Largest_Defect_um": round(largest, 2)
            },
            "Certification_Limits": {
                "Expected_Fatigue_Limit_MPa": None,
                "Design_Limit_MPa": None,
                "Hardness_Used_HV": None,
                "Status": NO_HARDNESS_STATUS
            }
        }

    # 3. Murakami & Gumbel Olasılıksal Analizi
    # evaluate_murakami_block fonksiyonunu kullanarak havacılık standartlarında rapor çekiyoruz.
    murakami_res = evaluate_murakami_block(
        defect_sqrt_areas_um=defect_sizes_um,
        hardness_HV=None, # Tablodaki alaşım sertliği (örn IN718 = 380 HV); alloy_id kayıt defteri id'si
        alloy_id=hardness_alloy_id
    )
    
    # Güven aralığı hesaplaması (%99 Survival)
    # Gumbel characteristic largest + X * scale verir, vb. Biz basitçe raporlanan fatigue limit'ten %10 sapma alalım 
    # veya doğrudan murakami'nin gumbel fit sonucunu gösterelim.
    gumbel_data = murakami_res.get("gumbel", {})
    char_defect = gumbel_data.get("characteristicLargest_um", max(defect_sizes_um))
    
    internal_fatigue = murakami_res.get("fatigueLimit_internal_MPa", 0)
    
    # Tasarım sınırı: sabit 0.85 katsayısı (istatistiksel %99 hayatta kalma sınırı DEĞİL; önceki
    # anahtar adı 99_Percent_Survival_Design_Limit_MPa bunu yanlış ifade ediyordu).
    design_limit = internal_fatigue * DESIGN_LIMIT_KNOCKDOWN

    report = {
        "modelStatus": MODEL_STATUS,
        "modelStatusNote": MODEL_STATUS_NOTE,
        "AI_Meltpool": {
            "Mean_Depth_um": round(mean_depth, 2),
            "Uncertainty_Std_um": round(std_depth, 2),
            "Confidence_Pct": round(surrogate_res["error_budget"]["confidence_pct"], 1)
        },
        "Defect_Simulation": {
            "Total_Defects_Found": len(defect_sizes_um),
            "Max_Simulated_Defect_um": round(max(defect_sizes_um), 2),
            "Gumbel_Predicted_Largest_Defect_um": round(char_defect, 2)
        },
        "Certification_Limits": {
            "Expected_Fatigue_Limit_MPa": internal_fatigue,
            "Design_Limit_MPa": round(design_limit, 2),
            "Design_Limit_Basis": DESIGN_LIMIT_BASIS,
            "Hardness_Used_HV": murakami_res.get("hardness_HV", 0),
            "Hardness_Source": murakami_res.get("hardnessSource")
        }
    }
    
    return report

if __name__ == "__main__":
    import sys
    try:
        if len(sys.argv) > 1:
            # Parse arguments: alloy, power, speed
            alloy = sys.argv[1]
            power = float(sys.argv[2])
            speed = float(sys.argv[3])
            res = run_industrial_fatigue_analysis(alloy, power, speed)
            print(json.dumps(res))
        else:
            # Default fallback for testing
            res = run_industrial_fatigue_analysis("IN718", 300, 1000)
            print(json.dumps(res, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
