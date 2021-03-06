
import numpy as np
import pandas as pd
from collections import defaultdict

__all__ = ["DataGenerator"]


class DataGenerator:

    def __init__(self, spec):
        """Create a DataGenerator based on a specification dictionary.

        The specification dictionary describes all of the tables and their
        constituent columns to generate. Nothing is generated at
        initialization; calls must be made to DataGenerator.make_chunk() to
        synthesize data.

        No validation is performed on the generator specification.
        """
        self.spec = spec
        self.tables = spec.keys()

    @staticmethod
    def _resolve_table_order(spec):
        """Determine the order in which tables must be built to satisfy the
        prerequisite requirements from a generator specification.

        Tables in the generator spec can contain prereq_tables and
        prereq_rows, and thus the referenced tables must be built before they
        can be used for the deriviative tables.

        There is no guarantee against circular, and thus impossible to
        construct, references.

        """
        all_tables = list(spec.keys())
        prereqs = []
        for table_name, table_spec in spec.items():
            if(table_spec.get("prereq_row", "") in all_tables):
                prereqs.append(table_spec["prereq_row"])
            for prereq_table in table_spec.get("prereq_tables", []):
                if prereq_table in all_tables:
                    prereqs.append(prereq_table)
        non_prereqs = set(all_tables) - set(prereqs)
        return prereqs + list(non_prereqs)

    def _add_to_list(self, generated_data, output_columns, split_column_names):
        """
        Takes either a single array, or a tuple of arrays each containing a
        different column of data, and appends the contents to the lists in
        the output_columns dictionary.

        The structure is output_columns[table_name] = list(np.array([]))

        Parameters
        ----------
        generated_data : tuple, list, or np.array().
            If a tuple or list is supplied, each entry is interpreted as a
            separate column identified by split_column_names.
        output_columns : dictionary
            Dictionary where the keys are column names, and the entries are
            lists of arrays containing the column data.
        split_column_names : list
            List of column names for the separate tuple elements of
            generated_data.

        """
        if isinstance(generated_data, tuple) or isinstance(generated_data, list):
            for i, name in enumerate(split_column_names):
                output_columns[name].append(generated_data[i])
        else:
            output_columns[split_column_names[0]].append(generated_data)
            if(len(split_column_names) > 1):
                assert ValueError, ("Column name implies multiple returns, "
                                    "but generator only returned one")

    def make_chunk(self, chunk_id, num_rows=None):
        """Generate synthetic data for one chunk.

        Parameters
        ----------
        chunk_id : int
                  ID of the chunk to generate.
        num_rows : int or dict
                  Generate the specified number of rows. Can either be a
                  scalar, or a dictionary of the form {table_name: num_rows}.

        Returns
        -------
        dictionary of pandas.DataFrames
            The output dictionary contains each generated table as a
            pandas.DataFrame.

        """

        output_tables = {}
        if isinstance(num_rows, dict):
            rows_per_table = dict(num_rows)
        else:
            rows_per_table = defaultdict(lambda: num_rows)

        for table in self._resolve_table_order(self.spec):
            column_generators = self.spec[table]["columns"]
            prereq_rows = self.spec[table].get("prereq_row", None)
            prereq_tables = self.spec[table].get("prereq_tables", [])
            output_columns = {}
            for column_name, column_generator in column_generators.items():

                split_column_names = column_name.split(",")
                for name in split_column_names:
                    output_columns[name] = []

                if prereq_rows is None:
                    individual_obj = column_generator(
                        chunk_id, rows_per_table[table],
                        prereq_tables={t: output_tables[t] for t in prereq_tables})
                    self._add_to_list(individual_obj, output_columns, split_column_names)
                else:
                    prereq_table_contents = {t: output_tables[t] for t in prereq_tables}
                    for n in range(len(output_tables[prereq_rows])):
                        individual_obj = column_generator(
                            chunk_id, rows_per_table[table],
                            prereq_row=output_tables[prereq_rows].iloc[n],
                            prereq_tables=prereq_table_contents)
                        self._add_to_list(individual_obj, output_columns, split_column_names)

            for name in output_columns.keys():
                temp = np.concatenate(output_columns[name])
                output_columns[name] = temp

            output_tables[table] = pd.DataFrame(output_columns)

        return output_tables
