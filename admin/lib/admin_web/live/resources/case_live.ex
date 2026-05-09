defmodule AdminWeb.Live.CaseLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.CasePart,
      update_changeset: &Admin.Schema.CasePart.changeset/3,
      create_changeset: &Admin.Schema.CasePart.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.case_part/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "Case"

  @impl Backpex.LiveResource
  def plural_name, do: "Cases"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      size: %{module: Backpex.Fields.Text, label: "Size (e.g. mid_tower, sff)"},
      supported_mobo_form_factors_input: %{module: Backpex.Fields.Text, label: "Supported Mobo Form Factors (comma-separated, e.g. atx, matx, itx)"},
      max_gpu_length_mm: %{module: Backpex.Fields.Number, label: "Max GPU Length (mm)"},
      max_cooler_height_mm: %{module: Backpex.Fields.Number, label: "Max Cooler Height (mm)"},
      max_radiator_front_mm: %{module: Backpex.Fields.Number, label: "Max Front Radiator (mm)"},
      max_radiator_top_mm: %{module: Backpex.Fields.Number, label: "Max Top Radiator (mm)"},
      max_psu_length_mm: %{module: Backpex.Fields.Number, label: "Max PSU Length (mm)"},
      included_fan_count: %{module: Backpex.Fields.Number, label: "Included Fans"},
      chamber_count: %{module: Backpex.Fields.Number, label: "Chambers"},
      front_panel_mesh: %{module: Backpex.Fields.Boolean, label: "Front Mesh Panel"},
      color: %{module: Backpex.Fields.Text, label: "Color"},
      drive_bays_35: %{module: Backpex.Fields.Number, label: "3.5\" Drive Bays"},
      drive_bays_25: %{module: Backpex.Fields.Number, label: "2.5\" Drive Bays"},
      max_fan_slots: %{module: Backpex.Fields.Number, label: "Max Fan Slots"},
      has_glass_panel: %{module: Backpex.Fields.Boolean, label: "Tempered Glass"},
      weight_kg: %{module: Backpex.Fields.Number, label: "Weight (kg)"},
      length_mm: %{module: Backpex.Fields.Number, label: "Length (mm)"},
      width_mm: %{module: Backpex.Fields.Number, label: "Width (mm)"},
      height_mm: %{module: Backpex.Fields.Number, label: "Height (mm)"},
      usb_front_type_a: %{module: Backpex.Fields.Number, label: "Front USB-A"},
      usb_front_type_c: %{module: Backpex.Fields.Number, label: "Front USB-C"}
    ]
  end
end
