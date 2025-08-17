package com.ba.bluearchivemusicapi.specifications;

import com.ba.bluearchivemusicapi.entities.OST;
import jakarta.persistence.criteria.JoinType;
import jakarta.persistence.criteria.Path;
import org.springframework.data.jpa.domain.Specification;

public class OstSpecifications {
    public static Specification<OST> byFieldAndValue(String fieldName, String filterValue) {
        return (root, query, cb) -> {
            // this solves the issue when count query has error with fetch join
            // see this for more info: https://github.com/spring-projects/spring-data-jpa/issues/532
            if (query != null && Long.class != query.getResultType()) {
                root.fetch("ostType", JoinType.LEFT);
            } else {
                root.join("ostType", JoinType.LEFT);
            }

            // when no filtering needed
            if (fieldName == null || filterValue == null ) {
                return null;
            }
            Path<String> fieldPath = fieldName.contains(".") ?
                    root.get(fieldName.split("\\.")[0]).get(fieldName.split("\\.")[1]) :
                    root.get(fieldName);

            // return a predicate or null
            if (fieldPath.getJavaType().equals(String.class)) {
                return cb.like(cb.upper(fieldPath), "%" + filterValue.toUpperCase() + "%");
            } else if (fieldPath.getJavaType().equals(Integer.class)) {
                try {
                    Integer parsedInt = Integer.parseInt(filterValue);
                    return cb.equal(fieldPath, parsedInt);
                } catch (NumberFormatException e) {
                    return null;
                }
            } else return null;

        }; // this whole Lambda = Specification<OST>
    }
}
