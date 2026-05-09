defmodule AdminWeb.Live.PSULive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.PSU,
      update_changeset: &Admin.Schema.PSU.changeset/3,
      create_changeset: &Admin.Schema.PSU.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.psu/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "PSU"

  @impl Backpex.LiveResource
  def plural_name, do: "PSUs"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      wattage: %{module: Backpex.Fields.Number, label: "Wattage"},
      form_factor: %{module: Backpex.Fields.Text, label: "Form Factor (e.g. atx, sfx)"},
      efficiency_rating: %{module: Backpex.Fields.Text, label: "Efficiency Rating (e.g. 80plus_gold)"},
      pcie_8pin_connectors: %{module: Backpex.Fields.Number, label: "PCIe 8-pin Connectors"},
      pcie_12pin_connectors: %{module: Backpex.Fields.Number, label: "PCIe 12-pin Connectors"},
      pcie_16pin_connectors: %{module: Backpex.Fields.Number, label: "PCIe 16-pin Connectors"},
      depth_mm: %{module: Backpex.Fields.Number, label: "Depth (mm)"},
      modular: %{module: Backpex.Fields.Text, label: "Modular (full/semi/non)"},
      eps_connectors: %{module: Backpex.Fields.Number, label: "EPS Connectors"},
      fan_size_mm: %{module: Backpex.Fields.Number, label: "Fan Size (mm)"},
      is_fanless: %{module: Backpex.Fields.Boolean, label: "Fanless"}
    ]
  end
end
