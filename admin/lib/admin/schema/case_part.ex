defmodule Admin.Schema.CasePart do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, Ecto.UUID, autogenerate: true}

  schema "cases" do
    field :name, :string, virtual: true
    field :manufacturer, :string, virtual: true
    field :model_number, :string, virtual: true
    field :year_released, :integer, virtual: true
    field :is_active, :boolean, virtual: true, default: true

    field :supported_mobo_form_factors, {:array, :string}
    field :max_gpu_length_mm, :integer
    field :max_cooler_height_mm, :integer
    field :max_radiator_front_mm, :integer
    field :max_radiator_top_mm, :integer
    field :max_psu_length_mm, :integer
    field :included_fan_count, :integer
    field :chamber_count, :integer
    field :front_panel_mesh, :boolean
    field :color, :string
    field :size, :string
    field :drive_bays_35, :integer
    field :drive_bays_25, :integer
    field :max_fan_slots, :integer
    field :has_glass_panel, :boolean
    field :weight_kg, :float
    field :length_mm, :integer
    field :width_mm, :integer
    field :height_mm, :integer
    field :usb_front_type_a, :integer
    field :usb_front_type_c, :integer

    field :supported_mobo_form_factors_input, :string, virtual: true
  end

  def changeset(case_part, attrs, _metadata \\ %{}) do
    case_part
    |> cast(attrs, [
      :name, :manufacturer, :model_number, :year_released, :is_active,
      :max_gpu_length_mm, :max_cooler_height_mm, :max_radiator_front_mm,
      :max_radiator_top_mm, :max_psu_length_mm, :included_fan_count,
      :chamber_count, :front_panel_mesh, :color, :size,
      :drive_bays_35, :drive_bays_25, :max_fan_slots, :has_glass_panel,
      :weight_kg, :length_mm, :width_mm, :height_mm,
      :usb_front_type_a, :usb_front_type_c,
      :supported_mobo_form_factors_input
    ])
    |> convert_array(:supported_mobo_form_factors_input, :supported_mobo_form_factors)
    |> validate_required([:name, :max_gpu_length_mm, :max_cooler_height_mm, :size, :supported_mobo_form_factors])
    |> prepare_changes(&upsert_pc_part(&1, "case"))
  end

  defp convert_array(changeset, from_field, to_field) do
    case get_change(changeset, from_field) do
      nil -> changeset
      "" -> put_change(changeset, to_field, [])
      str -> put_change(changeset, to_field, str |> String.split(~r/,\s*/) |> Enum.reject(&(&1 == "")))
    end
  end

  defp upsert_pc_part(changeset, part_type) do
    repo = changeset.repo
    id = get_field(changeset, :id)

    %Admin.Schema.PCPart{id: id}
    |> Ecto.Changeset.cast(
      %{
        name: get_field(changeset, :name),
        manufacturer: get_field(changeset, :manufacturer),
        model_number: get_field(changeset, :model_number),
        year_released: get_field(changeset, :year_released),
        is_active: get_field(changeset, :is_active) || true,
        part_type: part_type
      },
      [:name, :manufacturer, :model_number, :year_released, :is_active, :part_type]
    )
    |> repo.insert!(
      on_conflict: {:replace_all_except, [:id, :part_type, :created_at]},
      conflict_target: :id
    )

    changeset
  end
end
