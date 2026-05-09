defmodule AdminWeb.Live.MotherboardLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.Motherboard,
      update_changeset: &Admin.Schema.Motherboard.changeset/3,
      create_changeset: &Admin.Schema.Motherboard.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.motherboard/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "Motherboard"

  @impl Backpex.LiveResource
  def plural_name, do: "Motherboards"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      socket: %{module: Backpex.Fields.Text, label: "Socket"},
      form_factor: %{module: Backpex.Fields.Text, label: "Form Factor"},
      ddr_generation: %{module: Backpex.Fields.Text, label: "DDR Generation"},
      memory_slots: %{module: Backpex.Fields.Number, label: "Memory Slots"},
      has_wifi: %{module: Backpex.Fields.Boolean, label: "Wi-Fi"},
      m2_slots: %{module: Backpex.Fields.Number, label: "M.2 Slots"},
      m2_pcie_gen: %{module: Backpex.Fields.Number, label: "M.2 PCIe Gen"},
      chipset: %{module: Backpex.Fields.Text, label: "Chipset"},
      max_memory_gb: %{module: Backpex.Fields.Number, label: "Max Memory (GB)"},
      sata_ports: %{module: Backpex.Fields.Number, label: "SATA Ports"},
      pcie_x16_slots: %{module: Backpex.Fields.Number, label: "PCIe x16 Slots"},
      pcie_generation: %{module: Backpex.Fields.Number, label: "PCIe Generation"},
      has_bluetooth: %{module: Backpex.Fields.Boolean, label: "Bluetooth"},
      usb_type_a_count: %{module: Backpex.Fields.Number, label: "USB-A Ports"},
      usb_type_c_count: %{module: Backpex.Fields.Number, label: "USB-C Ports"},
      audio_codec: %{module: Backpex.Fields.Text, label: "Audio Codec"}
    ]
  end
end
