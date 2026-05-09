defmodule AdminWeb.Live.StorageLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.Storage,
      update_changeset: &Admin.Schema.Storage.changeset/3,
      create_changeset: &Admin.Schema.Storage.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.storage/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "Storage"

  @impl Backpex.LiveResource
  def plural_name, do: "Storage"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      storage_type: %{module: Backpex.Fields.Text, label: "Type (e.g. ssd, hdd)"},
      form_factor: %{module: Backpex.Fields.Text, label: "Form Factor (e.g. m2, 25)"},
      interface: %{module: Backpex.Fields.Text, label: "Interface (e.g. pcie_gen4, sata3)"},
      capacity_gb: %{module: Backpex.Fields.Number, label: "Capacity (GB)"},
      read_speed_mbps: %{module: Backpex.Fields.Number, label: "Read Speed (MB/s)"},
      write_speed_mbps: %{module: Backpex.Fields.Number, label: "Write Speed (MB/s)"},
      has_dram_cache: %{module: Backpex.Fields.Boolean, label: "DRAM Cache"},
      endurance_tbw: %{module: Backpex.Fields.Number, label: "Endurance (TBW)"},
      rpm: %{module: Backpex.Fields.Number, label: "RPM (HDD only)"}
    ]
  end
end
