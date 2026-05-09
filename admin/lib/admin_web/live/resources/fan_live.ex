defmodule AdminWeb.Live.FanLive do
  use Backpex.LiveResource,
    adapter: Backpex.Adapters.Ecto,
    adapter_config: [
      repo: Admin.Repo,
      schema: Admin.Schema.Fan,
      update_changeset: &Admin.Schema.Fan.changeset/3,
      create_changeset: &Admin.Schema.Fan.changeset/3,
      item_query: &AdminWeb.Live.PartQueries.fan/3
    ]

  @impl Backpex.LiveResource
  def layout(_assigns), do: {AdminWeb.Layouts, :backpex_passthrough}

  @impl Backpex.LiveResource
  def singular_name, do: "Fan"

  @impl Backpex.LiveResource
  def plural_name, do: "Fans"

  @impl Backpex.LiveResource
  def fields do
    [
      name: %{module: Backpex.Fields.Text, label: "Name"},
      manufacturer: %{module: Backpex.Fields.Text, label: "Manufacturer"},
      model_number: %{module: Backpex.Fields.Text, label: "Model Number"},
      year_released: %{module: Backpex.Fields.Number, label: "Year"},
      is_active: %{module: Backpex.Fields.Boolean, label: "Active"},
      size_mm: %{module: Backpex.Fields.Number, label: "Size (mm)"},
      max_rpm: %{module: Backpex.Fields.Number, label: "Max RPM"},
      airflow_cfm: %{module: Backpex.Fields.Number, label: "Airflow (CFM)"},
      noise_dba: %{module: Backpex.Fields.Number, label: "Noise (dBA)"},
      is_pwm: %{module: Backpex.Fields.Boolean, label: "PWM"},
      has_rgb: %{module: Backpex.Fields.Boolean, label: "RGB"},
      bearing_type: %{module: Backpex.Fields.Text, label: "Bearing Type"},
      is_static_pressure: %{module: Backpex.Fields.Boolean, label: "Static Pressure Optimized"},
      pack_count: %{module: Backpex.Fields.Number, label: "Pack Count"}
    ]
  end
end
