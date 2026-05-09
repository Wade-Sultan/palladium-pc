defmodule AdminWeb.Live.CPUCoolerLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.CPUCooler,
      update_changeset: &Admin.Schema.CPUCooler.changeset/3,
      create_changeset: &Admin.Schema.CPUCooler.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.cpu_cooler/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "CPU Cooler"

  @impl Backpex.LiveResource
  def plural_name, do: "CPU Coolers"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      cooler_type: %{module: Backpex.Fields.Text, label: "Type (e.g. air, aio_240)"},
      supported_sockets_input: %{module: Backpex.Fields.Text, label: "Supported Sockets (comma-separated, e.g. lga1700, am5)"},
      max_tdp_watts: %{module: Backpex.Fields.Number, label: "Max TDP (Watts)"},
      height_mm: %{module: Backpex.Fields.Number, label: "Height (mm)"},
      radiator_size_mm: %{module: Backpex.Fields.Number, label: "Radiator Size (mm)"},
      fan_count: %{module: Backpex.Fields.Number, label: "Fan Count"},
      fan_size_mm: %{module: Backpex.Fields.Number, label: "Fan Size (mm)"},
      noise_dba: %{module: Backpex.Fields.Number, label: "Noise (dBA)"},
      has_rgb: %{module: Backpex.Fields.Boolean, label: "RGB"}
    ]
  end
end
