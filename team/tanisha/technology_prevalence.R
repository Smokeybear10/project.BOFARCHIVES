# Technology Type Prevalence — BOF Subjects Considered, 1897–1908
# Author: Tanisha
# Three visualizations of how military technology categories appeared
# and shifted in BOF Annual Report subjects across nine reporting periods.
#
# Interactive Claude artifacts:
#   Stacked bars : https://claude.ai/public/artifacts/4e808fc7-355c-40ff-8b60-1998714aab7e
#   Heatmap      : https://claude.ai/public/artifacts/033a81ba-eca7-409b-8186-843ec0dc7e78
#   Ranking      : https://claude.ai/public/artifacts/97b0457f-1ce0-4424-8d15-b335e6a9bfd9
#
# This file is the canonical R source for the analysis. The dashboard
# (Plotly versions in bof_pipeline/tanisha_charts.py) is a port of this
# code with Tanisha's exact data and color palette preserved.

library(ggplot2)
library(tidyr)
library(dplyr)

# --- Data: counts by period × technology category ---
data <- data.frame(
  Period = c("1897-98","1898-99","1900-01","1901-02",
             "1903-04","1904-05","1905-06","1906-07","1907-08"),

  Aerial_Aviation            = c(29,51,1,5,18,4,7,8,13),
  Artillery_Guns             = c(68,39,38,53,52,38,31,32,25),
  Projectiles_Ammunition     = c(130,22,27,28,22,18,20,23,22),
  Explosives_Propellants     = c(23,9,9,7,8,5,1,3,4),
  Torpedoes_Mines            = c(42,6,3,3,9,12,8,5,8),
  Range_Finding_Fire_Control = c(17,12,9,13,17,14,18,10,15),
  Wireless_Electrical        = c(4,5,2,8,2,1,0,0,3),
  Armor_Fortification        = c(23,4,3,9,17,11,6,9,7),
  Searchlights_Optics        = c(2,2,3,3,10,7,5,22,10),
  Small_Arms                 = c(9,4,4,14,9,5,7,4,3),
  Transportation_Vehicles    = c(2,2,3,5,5,0,4,0,4),
  Entrenching_Field_Equip    = c(0,3,10,10,8,7,3,1,0),
  Other                      = c(48,20,13,52,41,17,23,25,34)
)

# --- Reshape to long format ---
data_long <- data |>
  pivot_longer(-Period, names_to = "Category", values_to = "Count") |>
  mutate(
    Period = factor(Period, levels = unique(data$Period)),
    Category = recode(Category,
      "Aerial_Aviation"            = "Aerial / Aviation",
      "Artillery_Guns"             = "Artillery & Guns",
      "Projectiles_Ammunition"     = "Projectiles & Ammunition",
      "Explosives_Propellants"     = "Explosives & Propellants",
      "Torpedoes_Mines"            = "Torpedoes & Mines",
      "Range_Finding_Fire_Control" = "Range Finding & Fire Control",
      "Wireless_Electrical"        = "Wireless & Electrical",
      "Armor_Fortification"        = "Armor & Fortification",
      "Searchlights_Optics"        = "Searchlights & Optics",
      "Small_Arms"                 = "Small Arms",
      "Transportation_Vehicles"    = "Transportation & Vehicles",
      "Entrenching_Field_Equip"    = "Entrenching & Field Equip.",
      "Other"                      = "Other"
    )
  )

# --- Color palette ---
my_colors <- c(
  "Aerial / Aviation"            = "#378ADD",
  "Artillery & Guns"             = "#1D9E75",
  "Projectiles & Ammunition"     = "#D85A30",
  "Explosives & Propellants"     = "#D4537E",
  "Torpedoes & Mines"            = "#888780",
  "Range Finding & Fire Control" = "#639922",
  "Wireless & Electrical"        = "#BA7517",
  "Armor & Fortification"        = "#534AB7",
  "Searchlights & Optics"        = "#185FA5",
  "Small Arms"                   = "#0F6E56",
  "Transportation & Vehicles"    = "#993C1D",
  "Entrenching & Field Equip."   = "#3B6D11",
  "Other"                        = "#5F5E5A"
)

# ─────────────────────────────────────────────────────────────────────────
# 1. Stacked bar chart (counts)
# ─────────────────────────────────────────────────────────────────────────
ggplot(data_long, aes(x = Period, y = Count, fill = Category)) +
  geom_bar(stat = "identity") +
  scale_fill_manual(values = my_colors) +
  labs(
    title = "Technology Type Prevalence by Period",
    subtitle = "Board of Ordnance & Fortification Annual Reports, 1897–1908",
    x = NULL, y = "Number of subjects", fill = NULL
  ) +
  theme_minimal(base_size = 13) +
  theme(
    legend.position = "bottom",
    legend.key.size = unit(0.4, "cm"),
    panel.grid.major.x = element_blank(),
    plot.title = element_text(face = "bold"),
    axis.text.x = element_text(angle = 45, hjust = 1)
  ) +
  guides(fill = guide_legend(nrow = 3))

# ─────────────────────────────────────────────────────────────────────────
# 2. Heatmap — global scale + row-normalized variant
# ─────────────────────────────────────────────────────────────────────────
heat_long <- data_long |>
  mutate(Category = factor(Category, levels = rev(c(
    "Projectiles & Ammunition","Artillery & Guns","Other","Torpedoes & Mines",
    "Aerial / Aviation","Armor & Fortification","Explosives & Propellants",
    "Range Finding & Fire Control","Small Arms","Searchlights & Optics",
    "Entrenching & Field Equip.","Transportation & Vehicles","Wireless & Electrical"
  ))))

# Global-scale (cells colored vs the overall max of 130)
ggplot(heat_long, aes(x = Period, y = Category, fill = Count)) +
  geom_tile(color = "#faf9f6", linewidth = 1.5) +
  geom_text(aes(label = Count), size = 3, fontface = "bold",
            color = ifelse(heat_long$Count > 50, "white", "#0C447C")) +
  scale_fill_gradientn(
    colors = c("#E6F1FB","#B5D4F4","#85B7EB","#378ADD","#185FA5","#0C447C","#042C53"),
    name = "Subjects"
  ) +
  labs(
    title = "Technology prevalence heatmap by period",
    subtitle = "Board of Ordnance & Fortification Annual Reports, 1897–1908",
    x = NULL, y = NULL
  ) +
  theme_minimal(base_size = 12) +
  theme(
    axis.text.x = element_text(angle = 45, hjust = 1, color = "#5f5e5a"),
    panel.grid = element_blank(),
    plot.title = element_text(face = "bold", size = 14),
    legend.position = "right"
  )

# ─────────────────────────────────────────────────────────────────────────
# 3. Horizontal bar ranking — total subjects per category
# ─────────────────────────────────────────────────────────────────────────
totals <- data.frame(
  Category = c("Projectiles & Ammunition","Artillery & Guns","Other",
               "Torpedoes & Mines","Aerial / Aviation","Armor & Fortification",
               "Explosives & Propellants","Range Finding & Fire Control",
               "Small Arms","Searchlights & Optics","Entrenching & Field Equip.",
               "Transportation & Vehicles","Wireless & Electrical"),
  Total = c(312, 376, 273, 96, 136, 89, 69, 125, 59, 64, 42, 25, 25)
) |>
  mutate(
    Pct = round(Total / sum(Total) * 100, 1),
    Label = paste0(Total, "  (", Pct, "%)"),
    Category = factor(Category, levels = Category[order(Total)])
  )

ggplot(totals, aes(x = Total, y = Category, fill = Category)) +
  geom_col(width = 0.65) +
  geom_text(aes(label = Label), hjust = -0.08, size = 3.2, color = "#5f5e5a") +
  scale_fill_manual(values = my_colors, guide = "none") +
  scale_x_continuous(expand = expansion(mult = c(0, 0.22)),
                     name = "Total subjects (1897–1908)") +
  labs(title = "Technology category ranking by total subjects",
       subtitle = "Board of Ordnance & Fortification Annual Reports, 1897–1908",
       y = NULL) +
  theme_minimal(base_size = 13) +
  theme(panel.grid.major.y = element_blank(),
        plot.title = element_text(face = "bold", size = 14))
