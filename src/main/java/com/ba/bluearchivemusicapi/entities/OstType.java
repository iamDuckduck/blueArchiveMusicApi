package com.ba.bluearchivemusicapi.entities;

import jakarta.persistence.*;
import lombok.*;

import java.util.ArrayList;
import java.util.List;

@Setter
@Getter
@AllArgsConstructor
@NoArgsConstructor
@Builder
@Entity
@Table(name = "ost_type")
public class OstType {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "volume")
    private Integer volume;

    @Column(name = "name")
    private String name;


    @OneToMany(mappedBy = "ostType")
    @Builder.Default
    private List<OST> addresses = new ArrayList<>();

}
