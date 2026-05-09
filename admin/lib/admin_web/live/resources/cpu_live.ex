defmodule AdminWeb.Live.CPULive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.CPU,
      update_changeset: &Admin.Schema.CPU.changeset/3,
      create_changeset: &Admin.Schema.CPU.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.cpu/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "CPU"

  @impl Backpex.LiveResource
  def plural_name, do: "CPUs"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      brand: %{module: Backpex.Fields.Text, label: "Brand"},
      socket: %{module: Backpex.Fields.Text, label: "Socket"},
      tdp_watts: %{module: Backpex.Fields.Number, label: "TDP (Watts)"},
      has_igpu: %{module: Backpex.Fields.Boolean, label: "Has iGPU"},
      ddr_generation_input: %{module: Backpex.Fields.Text, label: "DDR Generation (comma-separated, e.g. ddr4, ddr5)"},
      cores: %{module: Backpex.Fields.Number, label: "Cores"},
      threads: %{module: Backpex.Fields.Number, label: "Threads"},
      base_clock_ghz: %{module: Backpex.Fields.Number, label: "Base Clock (GHz)"},
      boost_clock_ghz: %{module: Backpex.Fields.Number, label: "Boost Clock (GHz)"},
      l3_cache_mb: %{module: Backpex.Fields.Number, label: "L3 Cache (MB)"},
      pcie_generation: %{module: Backpex.Fields.Number, label: "PCIe Generation"},
      max_memory_gb: %{module: Backpex.Fields.Number, label: "Max Memory (GB)"},
      series: %{module: Backpex.Fields.Text, label: "Series"},
      supported_features_input: %{module: Backpex.Fields.Text, label: "Supported Features (comma-separated)"},
      benchmark_scores_input: %{module: Backpex.Fields.Textarea, label: "Benchmark Scores (JSON)"}
    ]
  end
end
