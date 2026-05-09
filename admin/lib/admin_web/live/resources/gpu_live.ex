defmodule AdminWeb.Live.GPULive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.GPU,
      update_changeset: &Admin.Schema.GPU.changeset/3,
      create_changeset: &Admin.Schema.GPU.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.gpu/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "GPU"

  @impl Backpex.LiveResource
  def plural_name, do: "GPUs"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      chipset: %{module: Backpex.Fields.Text, label: "Chipset"},
      brand: %{module: Backpex.Fields.Text, label: "Brand"},
      vram_gb: %{module: Backpex.Fields.Number, label: "VRAM (GB)"},
      tdp_watts: %{module: Backpex.Fields.Number, label: "TDP (Watts)"},
      length_mm: %{module: Backpex.Fields.Number, label: "Length (mm)"},
      pcie_power_pins: %{module: Backpex.Fields.Text, label: "PCIe Power Pins"},
      recommended_psu_watts: %{module: Backpex.Fields.Number, label: "Recommended PSU (Watts)"},
      vram_type: %{module: Backpex.Fields.Text, label: "VRAM Type"},
      width_slots: %{module: Backpex.Fields.Number, label: "Width (slots)"},
      pcie_generation: %{module: Backpex.Fields.Number, label: "PCIe Generation"},
      base_clock_mhz: %{module: Backpex.Fields.Number, label: "Base Clock (MHz)"},
      boost_clock_mhz: %{module: Backpex.Fields.Number, label: "Boost Clock (MHz)"},
      has_ray_tracing: %{module: Backpex.Fields.Boolean, label: "Ray Tracing"},
      cuda_cores: %{module: Backpex.Fields.Number, label: "CUDA Cores"},
      tensor_cores: %{module: Backpex.Fields.Number, label: "Tensor Cores"},
      stream_processors: %{module: Backpex.Fields.Number, label: "Stream Processors"},
      matrix_cores: %{module: Backpex.Fields.Number, label: "Matrix Cores"},
      display_outputs: %{module: Backpex.Fields.Text, label: "Display Outputs"},
      hdmi_version: %{module: Backpex.Fields.Text, label: "HDMI Version"},
      dp_version: %{module: Backpex.Fields.Text, label: "DisplayPort Version"},
      supported_features_input: %{module: Backpex.Fields.Text, label: "Supported Features (comma-separated)"},
      benchmark_scores_input: %{module: Backpex.Fields.Textarea, label: "Benchmark Scores (JSON)"}
    ]
  end
end
