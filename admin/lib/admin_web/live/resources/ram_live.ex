defmodule AdminWeb.Live.RAMLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.RAM,
      update_changeset: &Admin.Schema.RAM.changeset/3,
      create_changeset: &Admin.Schema.RAM.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.ram/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "RAM Kit"

  @impl Backpex.LiveResource
  def plural_name, do: "RAM Kits"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      ddr_generation: %{module: Backpex.Fields.Text, label: "DDR Generation"},
      speed_mhz: %{module: Backpex.Fields.Number, label: "Speed (MHz)"},
      modules: %{module: Backpex.Fields.Number, label: "Modules"},
      capacity_gb: %{module: Backpex.Fields.Number, label: "Total Capacity (GB)"},
      height_mm: %{module: Backpex.Fields.Number, label: "Height (mm)"},
      module_capacity_gb: %{module: Backpex.Fields.Number, label: "Per-Module Capacity (GB)"},
      cas_latency: %{module: Backpex.Fields.Number, label: "CAS Latency"},
      voltage: %{module: Backpex.Fields.Number, label: "Voltage (V)"},
      has_rgb: %{module: Backpex.Fields.Boolean, label: "RGB"},
      is_ecc: %{module: Backpex.Fields.Boolean, label: "ECC"}
    ]
  end
end
