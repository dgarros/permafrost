
    # def diff(self, other: Self) -> HashableModelDiff:
    #     in_both, local_only, other_only = compare_lists(
    #         list1=self._get_field_names_for_diff(), list2=other._get_field_names_for_diff()
    #     )
    #     diff_result = HashableModelDiff(added=dict.fromkeys(local_only), removed=dict.fromkeys(other_only))

    #     for field_name in in_both:
    #         if field_name.startswith("_") or field_name in self._exclude_from_hash:
    #             continue

    #         local_value = getattr(self, field_name)
    #         other_value = getattr(other, field_name)
    #         local_signatures = self._get_signature_field(local_value)
    #         other_signatures = other._get_signature_field(other_value)

    #         if local_signatures != other_signatures:
    #             if isinstance(local_value, HashableModel) and isinstance(other_value, HashableModel):
    #                 diff_result.changed[field_name] = local_value.diff(other=other_value)
    #             else:
    #                 diff_result.changed[field_name] = None

    #     return diff_result